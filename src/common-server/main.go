package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"os/exec"
	"os/signal"
	"syscall"
	"time"

	"github.com/kr/pretty"
	"github.com/spiffe/spire/cmd/spire-server/util"
)

const (
	port         = 8090
	dlgUrl       = "http://ledger-gateway:8081"
	federationID = "test"
)

var trustDomainName string

// TODO use protobuff to DRY this definition
type BundleRequest struct {
	FederationID    string
	QualifiedBundle QualifiedBundle
}

type QualifiedBundle struct {
	RawBundle       string
	TrustDomainName string
}

type BundleResponse struct {
	QualifiedBundles []QualifiedBundle
}

func main() {
	trustDomainName = os.Getenv("TRUST_DOMAIN_NAME")
	if trustDomainName == "" {
		panic("need to provide a TRUST_DOMAIN_NAME")
	}

	cmd := exec.Command("/opt/spire/bin/spire-server", "run")
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	cmd.Stdin = os.Stdin

	if err := cmd.Start(); err != nil {
		log.Fatalf("Failed to start spire-server: %v", err)
	}
	log.Printf("Started spire-server with PID %d", cmd.Process.Pid)

	go doBundleStuff()

	setUpGracefulShutdown(cmd)
}

func setUpGracefulShutdown(cmd *exec.Cmd) {
	_, cancel := context.WithCancel(context.Background())
	go handleSignals(cmd, cancel)

	// Wait for the child process to exit (keeps container alive)
	if err := cmd.Wait(); err != nil {
		log.Printf("spire-server exited with error: %v", err)
	} else {
		log.Println("spire-server exited normally")
	}

	// Cleanup
	cancel()
	time.Sleep(1 * time.Second) // Give time for logs to flush
	log.Println("common-server shutting down")
}

func handleSignals(cmd *exec.Cmd, cancel context.CancelFunc) {
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)

	<-sigChan
	log.Println("Received shutdown signal, forwarding to spire-server...")
	if err := cmd.Process.Signal(syscall.SIGTERM); err != nil {
		log.Printf("Failed to signal spire-server: %v", err)
	}
	cancel()
}

func getMyBundle() string {
	cmd := exec.Command("/opt/spire/bin/spire-server", "bundle", "show", "-format", "spiffe")

	var result bytes.Buffer
	cmd.Stdout = &result

	cmd.Stderr = os.Stderr
	cmd.Stdin = os.Stdin

	if err := cmd.Run(); err != nil {
		panic(fmt.Sprint("bundle show command did not work: %s", err))
	}
	return result.String()
}

func PostBundle(federationID string, bundle string) {
	request := BundleRequest{
		FederationID: federationID,
		QualifiedBundle: QualifiedBundle{
			RawBundle:       bundle,
			TrustDomainName: trustDomainName,
		},
	}

	jsonBody, err := json.Marshal(request)

	if err != nil {
		panic("cannot marshall the bundle request")
	}

	resp, err := http.Post(
		dlgUrl+"/bundle",
		"application/json",
		bytes.NewBuffer(jsonBody),
	)

	if err != nil {
		panic("cannot post bundle")
	}

	defer resp.Body.Close()

	if resp.StatusCode != http.StatusCreated {
		body, _ := io.ReadAll(resp.Body)
		panic(fmt.Errorf("status code is %d, body %s", resp.StatusCode, string(body)))
	}

	log.Print("bundle posted succesfully")
}

func doBundleStuff() {
	log.Print("sleeping before posting bundle")
	time.Sleep(1 * time.Second)

	var myBundle = getMyBundle()
	log.Println("read mybundle", myBundle)

	PostBundle("test", myBundle)

	log.Print("sleeping before fetching bundles")
	time.Sleep(4 * time.Second)

	var bundles = GetBundles()
	for i := range bundles {
		if myBundle == bundles[i].RawBundle {
			continue
		}

		log.Print(
			"calling bundle set on ",
			bundles[i].RawBundle,
			" domain ",
			bundles[i].TrustDomainName,
		)

		go doBundleSet(bundles[i].RawBundle, bundles[i].TrustDomainName)
	}

}

func doBundleSet(rawBundle string, trustDomainName string) {
	cmd := exec.Command("/opt/spire/bin/spire-server", "bundle", "set", "-format", "spiffe", "-id", trustDomainName)

	okk, err := util.ParseBundle([]byte(rawBundle), "spiffe", trustDomainName)
	if err != nil {
		log.Println(fmt.Errorf("parse original bundle: %s", err))
	}
	log.Println("pretty")
	log.Println(fmt.Sprintf("%# v\n", pretty.Formatter(okk)))

	log.Println("okk.String()")
	log.Println(okk.String())

	log.Println("bytes.NewBufferString(rawBundle).String()")
	log.Println(bytes.NewBufferString(rawBundle).String())

	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	cmd.Stdin = bytes.NewBufferString(rawBundle)

	if err := cmd.Run(); err != nil {
		panic(fmt.Sprint("bundle set command did not work: %s", err))
	}
}

func GetBundles() []QualifiedBundle {
	resp, err := http.Get(dlgUrl + "/bundles/" + federationID)
	if err != nil {
		panic("could not fetch the bundlse")
	}

	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		panic("unexpected status code while fetching the bundles")
	}

	var bundleResponse BundleResponse

	if err := json.NewDecoder(resp.Body).Decode(&bundleResponse); err != nil {
		panic("error while decoding the repsonse from the get bundles")
	}

	return bundleResponse.QualifiedBundles
}
