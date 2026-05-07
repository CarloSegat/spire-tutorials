package main

import (
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
	"sync"
	"time"
)

const (
	port               = 8080
	getBundlesEndpoint = "/bundles/"
)

type BundleRequest struct {
	FederationID    string `json:"FederationID"`
	QualifiedBundle QualifiedBundle `json:"QualifiedBundle"`
}

type QualifiedBundle struct {
	RawBundle       string
	TrustDomainName string
}

type BundleResponse struct {
	QualifiedBundles []QualifiedBundle
}

type DeleteBundleRequest struct {
	FederationID    string `json:"FederationID"`
	TrustDomainName string `json:"TrustDomainName"`
}

var storage map[string][]QualifiedBundle
var sseClients map[chan string]struct{}
var sseClientsMux sync.Mutex

func main() {
	storage = make(map[string][]QualifiedBundle)
	sseClients = make(map[chan string]struct{})
	mux := http.NewServeMux()
	mux.HandleFunc("POST /bundle", postBundle)
	mux.HandleFunc("PUT /bundle", updateBundle)
	mux.HandleFunc("DELETE /bundle", deleteBundle)
	mux.HandleFunc("GET /events", streamEvents)
	mux.HandleFunc(getBundlesEndpoint, getBundles)
	http.ListenAndServe(fmt.Sprintf(":%d", port), mux)
}

func postBundle(w http.ResponseWriter, r *http.Request) {
	var bundleReq BundleRequest
	if err := json.NewDecoder(r.Body).Decode(&bundleReq); err != nil {
		fmt.Println(err)
		http.Error(w, "Error decoding the body", http.StatusBadRequest)
		return
	}

	if bundleReq.QualifiedBundle.RawBundle == "" || bundleReq.QualifiedBundle.TrustDomainName == "" {
		http.Error(
			w,
			"need to provide both bundle and trust domain name",
			http.StatusBadRequest,
		)
		return
	}


	if _, ok := storage[bundleReq.FederationID]; !ok {
		storage[bundleReq.FederationID] = []QualifiedBundle{}
	}

	fmt.Println("appending bundle to FederationID ", bundleReq.FederationID)

	storage[bundleReq.FederationID] =
		append(
			storage[bundleReq.FederationID],
			bundleReq.QualifiedBundle,
		)

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(map[string]string{"status": "created"})
}

func updateBundle(w http.ResponseWriter, r *http.Request) {
	var bundleReq BundleRequest
	if err := json.NewDecoder(r.Body).Decode(&bundleReq); err != nil {
		fmt.Println(err)
		http.Error(w, "Error decoding the body", http.StatusBadRequest)
		return
	}

	if bundleReq.FederationID == "" {
		http.Error(
			w,
			"need to provide FederationID",
			http.StatusBadRequest,
		)
		return
	}

	if bundleReq.QualifiedBundle.RawBundle == "" || bundleReq.QualifiedBundle.TrustDomainName == "" {
		http.Error(
			w,
			"need to provide both bundle and trust domain name",
			http.StatusBadRequest,
		)
		return
	}

	// Initialize storage for FederationID if it doesn't exist
	if _, ok := storage[bundleReq.FederationID]; !ok {
		storage[bundleReq.FederationID] = []QualifiedBundle{}
	}

	bundles := storage[bundleReq.FederationID]
	
	// Find and overwrite the bundle with matching TrustDomainName
	found := false
	for i, bundle := range bundles {
		if bundle.TrustDomainName == bundleReq.QualifiedBundle.TrustDomainName {
			// Overwrite the existing bundle
			storage[bundleReq.FederationID][i] = bundleReq.QualifiedBundle
			found = true
			fmt.Printf("Updated bundle with TrustDomainName %s in FederationID %s\n", bundleReq.QualifiedBundle.TrustDomainName, bundleReq.FederationID)
			break
		}
	}

	// If not found, append it (upsert behavior)
	if !found {
		storage[bundleReq.FederationID] = append(bundles, bundleReq.QualifiedBundle)
		fmt.Printf("Created new bundle with TrustDomainName %s in FederationID %s\n", bundleReq.QualifiedBundle.TrustDomainName, bundleReq.FederationID)
	}

	broadcast("bundle_updated", map[string]interface{}{
		"federation_id": bundleReq.FederationID,
		"trust_domain": bundleReq.QualifiedBundle.TrustDomainName,
	})

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "updated"})
}

func getBundles(w http.ResponseWriter, r *http.Request) {
	federationID := strings.TrimPrefix(r.URL.Path, getBundlesEndpoint)

	if federationID == "" {
		http.Error(w, "need to provide federation ID in the URL", http.StatusBadRequest)
	}

	fmt.Println("federationid ", federationID)

	bundles, ok := storage[federationID]
	if !ok {
		bundles = []QualifiedBundle{}
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(BundleResponse{QualifiedBundles: bundles})
}

func deleteBundle(w http.ResponseWriter, r *http.Request) {
	var deleteReq DeleteBundleRequest
	if err := json.NewDecoder(r.Body).Decode(&deleteReq); err != nil {
		fmt.Println(err)
		http.Error(w, "Error decoding the body", http.StatusBadRequest)
		return
	}

	if deleteReq.FederationID == "" || deleteReq.TrustDomainName == "" {
		http.Error(
			w,
			"need to provide both FederationID and TrustDomainName",
			http.StatusBadRequest,
		)
		return
	}

	bundles, ok := storage[deleteReq.FederationID]
	if !ok {
		http.Error(w, "FederationID not found", http.StatusNotFound)
		return
	}

	// Find and remove the bundle with matching TrustDomainName
	found := false
	for i, bundle := range bundles {
		if bundle.TrustDomainName == deleteReq.TrustDomainName {
			// Remove the bundle from the slice
			storage[deleteReq.FederationID] = append(bundles[:i], bundles[i+1:]...)
			found = true
			fmt.Printf("Deleted bundle with TrustDomainName %s from FederationID %s\n", deleteReq.TrustDomainName, deleteReq.FederationID)
			break
		}
	}

	if !found {
		http.Error(w, "QualifiedBundle with specified TrustDomainName not found in FederationID", http.StatusNotFound)
		return
	}

	broadcast("bundle_deleted", map[string]interface{}{
		"federation_id": deleteReq.FederationID,
		"trust_domain": deleteReq.TrustDomainName,
	})

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "deleted"})
}

func streamEvents(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")

	events := make(chan string)

	sseClientsMux.Lock()
	sseClients[events] = struct{}{}
	sseClientsMux.Unlock()

	defer func() {
		sseClientsMux.Lock()
		delete(sseClients, events)
		sseClientsMux.Unlock()
		close(events)
	}()

	for {
		select {
		case event := <-events:
			fmt.Fprintf(w, "data: %s\n\n", event)
			w.(http.Flusher).Flush()
		case <-r.Context().Done():
			return
		}
	}
}

func broadcast(eventType string, data map[string]interface{}) {
	payload, _ := json.Marshal(data)
	event := fmt.Sprintf(`{"type": "%s", "timestamp": %d, "data": %s}`, eventType, time.Now().Unix(), string(payload))

	sseClientsMux.Lock()
	defer sseClientsMux.Unlock()

	for ch := range sseClients {
		select {
		case ch <- event:
		default:
		}
	}
}
