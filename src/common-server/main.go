package main

import (
	"context"
	"log"
	"os"
	"os/exec"
	"os/signal"
	"syscall"
	"time"
)

const (
	port       = 8090
	socketPath = "unix:///tmp/spire-agent/public/api.sock"
)

func main() {
	log.Print("ciao, I am a server :)")

	// Start spire-server as a child process
	cmd := exec.Command("/opt/spire/bin/spire-server", "run")
	cmd.Stdout = os.Stdout  // Pipe spire logs to container stdout
	cmd.Stderr = os.Stderr  // Pipe errors to container stderr
	cmd.Stdin = os.Stdin    // Optional: allow input if needed

	if err := cmd.Start(); err != nil {
		log.Fatalf("Failed to start spire-server: %v", err)
	}
	log.Printf("Started spire-server with PID %d", cmd.Process.Pid)

	// Optional: Add your custom server logic here (e.g., HTTP listener)
	// For now, just log and wait
	log.Printf("common-server is now running (would start listener on port %d or socket %s)", port, socketPath)

	// Set up signal handling for graceful shutdown
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
