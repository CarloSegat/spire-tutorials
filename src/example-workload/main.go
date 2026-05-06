package main

import (
	"bufio"
	"context"
	"crypto/x509"
	"fmt"
	"io"
	"net"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"time"

	"sync"

	"github.com/sirupsen/logrus"
	"github.com/spiffe/go-spiffe/v2/bundle/x509bundle"
	"github.com/spiffe/go-spiffe/v2/spiffeid"
	"github.com/spiffe/go-spiffe/v2/spiffetls"
	"github.com/spiffe/go-spiffe/v2/spiffetls/tlsconfig"
	"github.com/spiffe/go-spiffe/v2/workloadapi"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

var log *logrus.Logger
var myServerNumber int
var maxServerNumber int
var myPort int
var experiementFinished bool

func main() {
	if len(os.Args) != 5 {
		panic("need 5 arguments")
	}

	ctx, _ := context.WithCancel(context.Background())
	log = logrus.New()
	logPath := os.Args[2]
	initLoggerToFile(log, logPath)

	log.Printf("Starting workload, spiffe unix is %s", os.Getenv("SPIFFE_ENDPOINT_SOCKET"))

	myPort, _ = strconv.Atoi(os.Args[1])
	myServerNumber, _ = strconv.Atoi(os.Args[3])
	maxServerNumber, _ = strconv.Atoi(os.Args[4])

	log.Printf("workload port: %d", myPort)

	time.Sleep(2 * time.Second)
	
	go startWatchers(ctx)
	
	go listenn(ctx, myPort)
	
	wg := sync.WaitGroup{}
	
	// internal comms
	theirPorts := makeArray(myPort)
	log.Println("their ports", theirPorts)
	
	for _, theirPort := range theirPorts {
		wg.Add(1)
		go talk(ctx, theirPort, &wg, fmt.Sprintf("ping from %d", myPort))
	}

	wg.Wait()

	log.Println("All worklopads internal to the cluster have exchanged a message, clustersetup complete")
	log.Println("Experiment begins: attempting to send 1 message to each workload in each other cluster")

	// external comms
	
	for _, theirPort := range generateExternalPorts(myServerNumber, maxServerNumber) {
		wg.Add(1)
		go talk(ctx, theirPort, &wg, fmt.Sprintf("ping from %d", myPort))
	}
	wg.Wait()
	log.Println("All messages sent, experiemnt is finished")
	experiementFinished = true

	log.Println("experiementFinished ", experiementFinished)

	// defer wg.Wait()
	select {}
}

func initLoggerToFile(log *logrus.Logger, logPath string) {

	fullPath := filepath.Join(logPath, "workload.log")

	f, err := os.OpenFile(fullPath, os.O_RDWR|os.O_CREATE|os.O_APPEND, 0666)
	if err != nil {
		log.Fatalf("error opening file: %v", err)
	}
	wrt := io.MultiWriter(os.Stdout, f)

	log.SetOutput(wrt)
	
	// Configure formatter to include milliseconds in timestamp
	log.SetFormatter(&logrus.TextFormatter{
		TimestampFormat: "2006-01-02 15:04:05.000",
		FullTimestamp:   true,
	})
}

func makeArray(port int) []int {
	// Compute the base of the block n belongs to.
	// Each block is size 4, spaced by 6.
	blockOffset := (port - 8085) / 6 // which block number?
	base := 8085 + blockOffset*6  // starting value of the block

	result := []int{}
	for i := 0; i < 4; i++ {
		v := base + i
		if v != port {
			result = append(result, v)
		}
	}
	return result
}

func talk(ctx context.Context, theirPort int, wg *sync.WaitGroup, message string) {
	defer wg.Done()

	theirAddress := fmt.Sprintf("127.0.0.1:%d", theirPort)
	log.Printf("Talking setting up on address %s", theirAddress)

	var conn net.Conn
	var err error 
	for{
		conn, err = spiffetls.Dial(ctx,
			"tcp",
			theirAddress,
			tlsconfig.AuthorizeAny(),
		)
		if err == nil {
			log.Printf("Established TLS connection to %d", theirPort)
			break
		}

		log.Printf("Error in talk is %v", err)
		
		select {
			case <-ctx.Done():
				log.Warnf("Context canceled for %s: %v", theirAddress, ctx.Err())
				return // Bail out.
			case <-time.After(500 * time.Millisecond): // Short sleep.
        }
		
	}
	defer conn.Close()

	log.Printf("Attempting to talk to %s", theirAddress)

	// Send a message to the server using the TLS connection

	fmt.Fprintf(conn, "%s\n", message)

	log.Printf("Sent ping to %s", theirAddress)

	// Read server response
	// status, err := bufio.NewReader(conn).ReadString('\n')
	// if err != nil && err != io.EOF {
	// 	panic(fmt.Errorf("unable to read server response: %w", err))
	// }
	// log.Printf("Other workload says: %q", status)
}

func listenn(ctx context.Context, myPort int) {
	myAddress := fmt.Sprintf("127.0.0.1:%d", myPort)
	log.Printf("Listening setting up on address %s", myAddress)

	listener, err := spiffetls.ListenWithMode(ctx, "tcp", myAddress,
		spiffetls.MTLSServerWithSourceOptions(
			tlsconfig.AuthorizeAny(),
		))
	if err != nil {
		log.Errorf("unable to create TLS listener: %s", err)
		panic("noo")
	}
	defer listener.Close()

	// Handle connections
	for {
		conn, err := listener.Accept()
		if err != nil {
			log.Errorf("failed to accept connection: %s", err)
			panic("noo")
		}
		go handleConnection(conn)
	}
}

func startWatchers(ctx context.Context) {
	var wg sync.WaitGroup

	socketPath := os.Getenv("SPIFFE_ENDPOINT_SOCKET")
	client, err := workloadapi.New(ctx, workloadapi.WithAddr(socketPath))
	if err != nil {
		log.Fatalf("Unable to create workload API client: %v", err)
	}
	defer client.Close()

	wg.Add(1)
	go func() {
		defer wg.Done()
		err := client.WatchX509Bundles(ctx, &MyBundleWatcher{ctx: ctx})
		if err != nil && status.Code(err) != codes.Canceled {
			log.Fatalf("Error watching X.509 context: %v", err)
		}
	}()

	wg.Wait()
}

// x509Watcher is a sample implementation of the workloadapi.X509ContextWatcher interface
// type x509Watcher struct{}
type MyBundleWatcher struct {
	ctx                      context.Context
	previousBundleSerials   map[string][]string // trust domain -> []certificate serial numbers
	previousBundleSerialsMux sync.Mutex
}

// getBundleSerials extracts certificate serial numbers from a bundle
func getBundleSerials(bundle *x509bundle.Bundle) []string {
	authorities := bundle.X509Authorities()
	serials := make([]string, 0, len(authorities))
	for _, cert := range authorities {
		// cert is of type *x509.Certificate from crypto/x509 package
		var _ *x509.Certificate = cert // explicit type to satisfy linter
		serials = append(serials, cert.SerialNumber.String())
	}
	return serials
}

// compareSerials compares two serial slices and returns true if they differ
func compareSerials(s1, s2 []string) bool {
	if len(s1) != len(s2) {
		return true
	}
	// Sort both slices to compare regardless of order
	sort.Strings(s1)
	sort.Strings(s2)
	for i := range s1 {
		if s1[i] != s2[i] {
			return true
		}
	}
	return false
}

func (w *MyBundleWatcher) OnX509BundlesUpdate(boh *x509bundle.Set) {
	log.Println("509 update called", boh)

	myTrustDomain, err := spiffeid.TrustDomainFromString(deduceServerSpiffeID(myServerNumber))
	if err != nil {
		log.Println("could not create trust domain object")
		panic("could not create trust domain object")
	}

	myBundle, present := boh.Get(myTrustDomain)
	if !present {
		log.Println("bundle not found")
		panic("bundle not found")
	}

	log.Println("showing my bundle")
	log.Println("X509Authorities", len(myBundle.X509Authorities()))

	// Check if any federation bundle (not our own) has been updated
	w.previousBundleSerialsMux.Lock()
	if w.previousBundleSerials == nil {
		w.previousBundleSerials = make(map[string][]string)
	}

	var updatedServerNum int
	federationUpdated := false
	for serverNum := 1; serverNum <= maxServerNumber; serverNum++ {
		// Skip our own trust domain
		if serverNum == myServerNumber {
			continue
		}

		trustDomainStr := fmt.Sprintf("%d.snet.example", serverNum)
		trustDomain, err := spiffeid.TrustDomainFromString(trustDomainStr)
		if err != nil {
			continue
		}

		bundle, present := boh.Get(trustDomain)
		if !present {
			continue
		}

		// Get current certificate serial numbers
		currentSerials := getBundleSerials(bundle)
		previousSerials, hadPrevious := w.previousBundleSerials[trustDomainStr]

		// Check if this federation bundle has been updated
		if hadPrevious {
			if compareSerials(previousSerials, currentSerials) {
				log.Printf("Detected federation bundle update: %s certificate serials changed from %v to %v", 
					trustDomainStr, previousSerials, currentSerials)
				federationUpdated = true
				updatedServerNum = serverNum
			}
		} else {
			log.Printf("First time seeing federation bundle: %s with certificate serials %v", 
				trustDomainStr, currentSerials)
		}

		w.previousBundleSerials[trustDomainStr] = currentSerials
	}
	w.previousBundleSerialsMux.Unlock()

	if federationUpdated && experiementFinished {
		log.Printf("Federation bundle certificate serials updated for server %d - initiating communication after key rotation", updatedServerNum)
		go communicateAgainAfterKeyRotation(w.ctx, updatedServerNum)
	}

	log.Println(myBundle)

}

func (w *MyBundleWatcher) OnX509BundlesWatchError(err error) {
	log.Println("got somthing erroneous", err)
}

// getPortsForServer returns the 4 ports for a specific server number
func getPortsForServer(serverNum int) []int {
	base := 8085 + (serverNum-1)*6
	result := make([]int, 4)
	for i := 0; i < 4; i++ {
		result[i] = base + i
	}
	return result
}

// communicateAgainAfterKeyRotation sends a special message to peers after a new key is activated.
// It only sends messages to the 4 workloads belonging to the server whose bundle was updated.
func communicateAgainAfterKeyRotation(ctx context.Context, updatedServerNum int) {
	log.Printf("Starting special communication: communicating again after key rotation (targeting server %d)", updatedServerNum)

	theirPorts := getPortsForServer(updatedServerNum)
	log.Printf("Ports for post-rotation communication to server %d: %v", updatedServerNum, theirPorts)

	var wg sync.WaitGroup
	for _, theirPort := range theirPorts {
		wg.Add(1)
		go talk(ctx, theirPort, &wg, fmt.Sprintf("communicating again after key rotation from %d", myPort))
	}

	wg.Wait()
	log.Printf("Finished special communication: communicating again after key rotation (server %d)", updatedServerNum)
}

func handleConnection(conn net.Conn) {
	defer conn.Close()

	// Read incoming data into buffer
	req, err := bufio.NewReader(conn).ReadString('\n')
	if err != nil {
		if strings.Contains(err.Error(), "bad certificate"){
			// log.Printf("Certificate error: %v", err)
			return
		}
		log.Printf("Error reading incoming data: %v", err)
		return
	}

	trimmedReq := strings.TrimSpace(req)
	if strings.HasPrefix(trimmedReq, "communicating again after key rotation") {
		log.Printf("Received special post-rotation message: %q", trimmedReq)
	} else {
		log.Printf("Received message: %q", trimmedReq)
	}

	// Send a response back to the other workload
	if _, err = conn.Write([]byte("Pong\n")); err != nil {
		log.Printf("Unable to send response: %v", err)
		return
	}
}

func deduceServerSpiffeID(myServerNumber int) string {
	return fmt.Sprintf("%d.snet.example", myServerNumber)
}

func generateExternalPorts(myServer int, maxServer int) []int {
	result := []int{}
	for num := range maxServer {
		if num+1 == myServer {
			continue
		}
		base := 8085 + num*6 // starting value of the block

		result = append(result, base, base+1, base+2, base+3)
	}
	return result
}
