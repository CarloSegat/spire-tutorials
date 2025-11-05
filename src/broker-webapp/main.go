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
	"github.com/spiffe/go-spiffe/v2/bundle/jwtbundle"
	"github.com/spiffe/go-spiffe/v2/bundle/x509bundle"
	"github.com/spiffe/go-spiffe/v2/spiffetls"
	"github.com/spiffe/go-spiffe/v2/spiffetls/tlsconfig"
	"github.com/spiffe/go-spiffe/v2/workloadapi"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

var log *logrus.Logger

func main() {
	ctx, _ := context.WithCancel(context.Background())
	log = logrus.New()
	logPath := os.Args[2]
	initLoggerToFile(log, logPath)

	log.Printf("Starting workload, spiffe unix is %s", os.Getenv("SPIFFE_ENDPOINT_SOCKET"))

	myPort, err := strconv.Atoi(os.Args[1])
	if err != nil {
		panic(err)
	}

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

	theirPort := calculateTheirPort(myPort)
	go talk(ctx, theirPort)

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

func calculateTheirPort(myPort int) int {
	oddOrEven := myPort % 2
	if oddOrEven == 0 {
		return myPort - 1
	} else {
		return myPort + 1
	}
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
	log.Printf("Server says: %q", status)
}

func listenn(ctx context.Context, myPort int) {
	myAddress := fmt.Sprintf("127.0.0.1:%d", myPort)
	log.Printf("Listening setting up on address %s", myAddress)
	// listener, err := spiffetls.Listen(ctx, "tcp", myAddress, tlsconfig.AuthorizeAny())
	// if err != nil {
	// 	log.Error("unable to create TLS listener")
	// 	panic("unable to create TLS listener")
	// }
	// defer listener.Close()

	// log.Printf("Listening on %s", myAddress)

	// for {
	// 	conn, err := listener.Accept()
	// 	if err != nil {
	// 		panic(fmt.Errorf("failed to accept connection: %w", err))
	// 	}
	// 	log.Printf("connection accepted: %v\n", conn)
	// 	go handleConnection(conn)
	// }
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

	// Creates a new Workload API client, connecting to provided socket path
	// Environment variable `SPIFFE_ENDPOINT_SOCKET` is used as default

	socketPath := os.Getenv("SPIFFE_ENDPOINT_SOCKET")
	client, err := workloadapi.New(ctx, workloadapi.WithAddr(socketPath))
	if err != nil {
		log.Fatalf("Unable to create workload API client: %v", err)
	}
	defer client.Close()

//	wg.Add(1)
//	// Start a watcher for X.509 SVID updates
//	go func() {
//		defer wg.Done()
//		err := client.WatchX509Context(ctx, &x509Watcher{})
//		if err != nil && status.Code(err) != codes.Canceled {
//			log.Fatalf("Error watching X.509 context: %v", err)
//		}
//	}()

	wg.Add(1)
	go func() {
		defer wg.Done()
		err := client.WatchX509Bundles(ctx, &MyBundleWatcher{})
		if err != nil && status.Code(err) != codes.Canceled {
			log.Fatalf("Error watching X.509 context: %v", err)
		}
	}()


//	wg.Add(1)
	// Start a watcher for JWT bundle updates
//	go func() {
//		defer wg.Done()
//		err := client.WatchJWTBundles(ctx, &jwtWatcher{})
//		if err != nil && status.Code(err) != codes.Canceled {
//			log.Fatalf("Error watching JWT bundles: %v", err)
//		}
//	}()

	wg.Wait()
}

// x509Watcher is a sample implementation of the workloadapi.X509ContextWatcher interface
// type x509Watcher struct{}
type MyBundleWatcher struct {}

func (MyBundleWatcher) OnX509BundlesUpdate(boh *x509bundle.Set){
    log.Println("got somthing", boh)
}

func (MyBundleWatcher) OnX509BundlesWatchError(err error){
    log.Println("got somthing erroneous", err)
}

// UpdateX509SVIDs is run every time an SVID is updated
//func (x509Watcher) OnX509ContextUpdate(c *workloadapi.X509Context) {
//	for _, svid := range c.SVIDs {
//		pem, _, err := svid.Marshal()
//		if err != nil {
//			log.Fatalf("Unable to marshal X.509 SVID: %v", err)
//		}
//
//		log.Printf("SVID updated for %q: \n%s\n", svid.ID, string(pem))
//	}
//}

// OnX509ContextWatchError is run when the client runs into an error
//func (x509Watcher) OnX509ContextWatchError(err error) {
//	if status.Code(err) != codes.Canceled {
//		log.Printf("OnX509ContextWatchError error: %v", err)
//	}
//}

// jwtWatcher is a sample implementation of the workloadapi.JWTBundleWatcher interface
type jwtWatcher struct{}

// UpdateX509SVIDs is run every time a JWT Bundle is updated
func (jwtWatcher) OnJWTBundlesUpdate(bundleSet *jwtbundle.Set) {
	for _, bundle := range bundleSet.Bundles() {
		jwt, err := bundle.Marshal()
		if err != nil {
			log.Fatalf("Unable to marshal JWT Bundle : %v", err)
		}
		log.Printf("jwt bundle updated %q: %s", bundle.TrustDomain(), string(jwt))
	}
}

// OnJWTBundlesWatchError is run when the client runs into an error
func (jwtWatcher) OnJWTBundlesWatchError(err error) {
	if status.Code(err) != codes.Canceled {
		log.Printf("OnJWTBundlesWatchError error: %v", err)
	}
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

	// Send a response back to the client
	if _, err = conn.Write([]byte("Pong\n")); err != nil {
		log.Printf("Unable to send response: %v", err)
		return
	}
}
