package main

import (
	"encoding/json"
	"fmt"
	"net/http"
	"sync"
	"time"
)

const port = 9080

type Metadata struct {
	DomainName  string `json:"DomainName"`
	KeycloakURL string `json:"KeycloakURL"`
	JWKSURL     string `json:"JWKSURL"`
}

type RegisterRequest struct {
	FederationID string   `json:"FederationID"`
	Metadata     Metadata `json:"Metadata"`
}

type DeleteRequest struct {
	FederationID string `json:"FederationID"`
	DomainName   string `json:"DomainName"`
}

type ListResponse struct {
	Metadata []Metadata `json:"Metadata"`
}

var (
	storage       = map[string]map[string]Metadata{} // fid -> domain -> meta
	storageMux    sync.Mutex
	sseClients    = map[chan string]struct{}{}
	sseClientsMux sync.Mutex
)

func main() {
	mux := http.NewServeMux()
	mux.HandleFunc("POST /metadata/register", register)
	mux.HandleFunc("DELETE /metadata", del)
	mux.HandleFunc("GET /metadata", list)
	mux.HandleFunc("GET /events", streamEvents)
	addr := fmt.Sprintf(":%d", port)
	fmt.Printf("oauth-metadata-repo listening on %s\n", addr)
	http.ListenAndServe(addr, mux)
}

func register(w http.ResponseWriter, r *http.Request) {
	fid := r.URL.Query().Get("federation_id")
	if fid == "" {
		http.Error(w, "federation_id required", http.StatusBadRequest)
		return
	}
	var req RegisterRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	m := req.Metadata
	if m.DomainName == "" || m.KeycloakURL == "" || m.JWKSURL == "" {
		http.Error(w, "DomainName, KeycloakURL, JWKSURL required", http.StatusBadRequest)
		return
	}
	storageMux.Lock()
	if _, ok := storage[fid]; !ok {
		storage[fid] = map[string]Metadata{}
	}
	storage[fid][m.DomainName] = m
	storageMux.Unlock()

	broadcast("domain_added", fid, m)

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(map[string]string{"status": "registered"})
	fmt.Printf("registered %s in %s\n", m.DomainName, fid)
}

func del(w http.ResponseWriter, r *http.Request) {
	var req DeleteRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	if req.FederationID == "" || req.DomainName == "" {
		http.Error(w, "FederationID and DomainName required", http.StatusBadRequest)
		return
	}
	storageMux.Lock()
	m, ok := storage[req.FederationID][req.DomainName]
	if ok {
		delete(storage[req.FederationID], req.DomainName)
	}
	storageMux.Unlock()
	if !ok {
		http.Error(w, "not found", http.StatusNotFound)
		return
	}
	broadcast("domain_removed", req.FederationID, m)
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "deleted"})
	fmt.Printf("removed %s from %s\n", req.DomainName, req.FederationID)
}

func list(w http.ResponseWriter, r *http.Request) {
	fid := r.URL.Query().Get("federation_id")
	if fid == "" {
		http.Error(w, "federation_id required", http.StatusBadRequest)
		return
	}
	storageMux.Lock()
	out := []Metadata{}
	for _, m := range storage[fid] {
		out = append(out, m)
	}
	storageMux.Unlock()
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(ListResponse{Metadata: out})
}

func streamEvents(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")

	ch := make(chan string, 32)
	sseClientsMux.Lock()
	sseClients[ch] = struct{}{}
	sseClientsMux.Unlock()
	defer func() {
		sseClientsMux.Lock()
		delete(sseClients, ch)
		sseClientsMux.Unlock()
		close(ch)
	}()

	for {
		select {
		case ev := <-ch:
			fmt.Fprintf(w, "data: %s\n\n", ev)
			w.(http.Flusher).Flush()
		case <-r.Context().Done():
			return
		}
	}
}

func broadcast(eventType, fid string, m Metadata) {
	payload, _ := json.Marshal(map[string]interface{}{
		"type":          eventType,
		"timestamp":     time.Now().Unix(),
		"federation_id": fid,
		"domain_name":   m.DomainName,
		"keycloak_url":  m.KeycloakURL,
		"jwks_url":      m.JWKSURL,
	})
	sseClientsMux.Lock()
	defer sseClientsMux.Unlock()
	for ch := range sseClients {
		select {
		case ch <- string(payload):
		default:
		}
	}
}
