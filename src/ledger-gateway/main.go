package main

import (
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
)

const (
	port               = 8081
	getBundlesEndpoint = "/bundles/"
)

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

var storage map[string][]QualifiedBundle

func main() {
	storage = make(map[string][]QualifiedBundle)
	mux := http.NewServeMux()
	mux.HandleFunc("POST /bundle", postBundle)
	mux.HandleFunc(getBundlesEndpoint, getBundles)
	http.ListenAndServe(fmt.Sprintf(":%d", port), mux)
}

func postBundle(w http.ResponseWriter, r *http.Request) {
	var bundleReq BundleRequest
	if err := json.NewDecoder(r.Body).Decode(&bundleReq); err != nil {
		http.Error(w, "empty body", http.StatusBadRequest)
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

func getBundles(w http.ResponseWriter, r *http.Request) {
	bundleID := strings.TrimPrefix(r.URL.Path, getBundlesEndpoint)

	if bundleID == "" {
		http.Error(w, "need to provide ID in the URL", http.StatusBadRequest)
	}

	fmt.Println("bundleID ", bundleID)

	bundles, ok := storage[bundleID]
	if !ok {
		bundles = []QualifiedBundle{}
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(BundleResponse{QualifiedBundles: bundles})
}
