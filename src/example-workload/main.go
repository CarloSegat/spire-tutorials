package main

import (
	"bufio"
	"context"
	"fmt"
	"io"
	"net"
	"os"
	"path/filepath"
	"strconv"

	"sync"

	"github.com/sirupsen/logrus"
	"github.com/spiffe/go-spiffe/v2/bundle/x509bundle"
	"github.com/spiffe/go-spiffe/v2/spiffetls"
	"github.com/spiffe/go-spiffe/v2/spiffetls/tlsconfig"
	"github.com/spiffe/go-spiffe/v2/workloadapi"
        "github.com/spiffe/go-spiffe/v2/spiffeid"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

var log *logrus.Logger
var myServerNumber int
var maxServerNumber int

func main() {
	if len(os.Args) != 5 {
	    panic("need 5 arguments")
	}

	ctx, _ := context.WithCancel(context.Background())
	log = logrus.New()
	logPath := os.Args[2]
	initLoggerToFile(log, logPath)

	log.Printf("Starting workload, spiffe unix is %s", os.Getenv("SPIFFE_ENDPOINT_SOCKET"))


	myPort, _ := strconv.Atoi(os.Args[1])
	myServerNumber, _ = strconv.Atoi(os.Args[3])
	maxServerNumber, _ = strconv.Atoi(os.Args[4])


	log.Printf("workload port: %d", myPort)

	// source, err := workloadapi.NewX509Source(ctx)
	// if err != nil {
	// 	log.Errorf("unable to create X509Source: %s", err)
	// 	panic(err)
	// }
	// defer source.Close()

	// log.Printf("got source: %s", source)
	go startWatchers(ctx)

	go listenn(ctx, myPort)

	theirPorts := makeArray(myPort)
	log.Println("their ports", theirPorts)

	for _, theirPort := range theirPorts {
	    go talk(ctx, theirPort)
	}

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
}

func makeArray(n int) []int {
    // Compute the base of the block n belongs to.
    // Each block is size 4, spaced by 6.
    blockOffset := (n - 8083) / 6  // which block number?
    base := 8083 + blockOffset*6   // starting value of the block

    result := []int{}
    for i := 0; i < 4; i++ {
        v := base + i
        if v != n {
            result = append(result, v)
        }
    }
    return result
}

func talk(ctx context.Context, theirPort int) {
	theirAddress := fmt.Sprintf("127.0.0.1:%d", theirPort)
	log.Printf("Talking setting up on address %s", theirAddress)
	conn, err := spiffetls.Dial(ctx,
		"tcp",
		theirAddress,
		tlsconfig.AuthorizeAny(),
	)
	if err != nil {
		panic(fmt.Errorf("unable to create TLS connection: %w", err))
	}
	defer conn.Close()

	log.Printf("Attempting to talk to %s", theirAddress)

	// Send a message to the server using the TLS connection
	fmt.Fprintf(conn, "ping\n")

	log.Printf("Sent ping to %s, waiting for pong", theirAddress)

	// Read server response
	status, err := bufio.NewReader(conn).ReadString('\n')
	if err != nil && err != io.EOF {
		panic(fmt.Errorf("unable to read server response: %w", err))
	}
	log.Printf("Other workload says: %q", status)
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
		err := client.WatchX509Bundles(ctx, &MyBundleWatcher{})
		if err != nil && status.Code(err) != codes.Canceled {
			log.Fatalf("Error watching X.509 context: %v", err)
		}
	}()

	wg.Wait()
}

// x509Watcher is a sample implementation of the workloadapi.X509ContextWatcher interface
// type x509Watcher struct{}
type MyBundleWatcher struct {}

func (MyBundleWatcher) OnX509BundlesUpdate(boh *x509bundle.Set){
    log.Println("509 update called", boh)

    myTrustDomain, err := spiffeid.TrustDomainFromString( deduceServerSpiffeID(myServerNumber) )
    if err != nil {
        log.Println("could not create trust domain object")
	panic("could not create trust domain object")
    }

    myBundle, present:= boh.Get(myTrustDomain)
    if ! present {
	log.Println("bundle not found")
	panic("bundle not found")
    }

    log.Println("showing my bundle")
    log.Println("X509Authorities", len(myBundle.X509Authorities()))

    log.Println(myBundle)

}

func (MyBundleWatcher) OnX509BundlesWatchError(err error){
    log.Println("got somthing erroneous", err)
}

func handleConnection(conn net.Conn) {
	defer conn.Close()

	// Read incoming data into buffer
	req, err := bufio.NewReader(conn).ReadString('\n')
	if err != nil {
		log.Printf("Error reading incoming data: %v", err)
		return
	}
	log.Printf("Client says: %q", req)

	// Send a response back to the other workload
	if _, err = conn.Write([]byte("Pong\n")); err != nil {
		log.Printf("Unable to send response: %v", err)
		return
	}
}

func deduceServerSpiffeID(myServerNumber int) (string) {
    return fmt.Sprintf("%d.snet.example", myServerNumber)
}
