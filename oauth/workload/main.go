package main

import (
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"strings"
	"sync"
	"time"
)

type config struct {
	clientID        string
	clientSecret    string
	keycloakURL     string
	federationID    string
	domainName      string
	workloadName    string
	port            string
	peersFile       string
	noIntrospection bool
}

type tokenResp struct {
	AccessToken string `json:"access_token"`
	ExpiresIn   int    `json:"expires_in"`
	TokenType   string `json:"token_type"`
}

type cachedToken struct {
	value     string
	expiresAt time.Time
}

var (
	cfg config

	ownTokenMu sync.Mutex
	ownToken   *cachedToken

	exchangeMu sync.Mutex
	exchange   = map[string]*cachedToken{} // key: target_domain|target_url

	metaMu    sync.Mutex
	metaCache = map[string]string{} // domain_name -> keycloak_url
)

func main() {
	cfg = loadConfig()
	mux := http.NewServeMux()
	mux.HandleFunc("GET /api", handleAPI)
	mux.HandleFunc("POST /call", handleCall)
	mux.HandleFunc("GET /healthz", func(w http.ResponseWriter, r *http.Request) { w.WriteHeader(200) })
	addr := ":" + cfg.port
	fmt.Printf("workload %s (%s) listening on %s\n", cfg.workloadName, cfg.domainName, addr)
	http.ListenAndServe(addr, mux)
}

func loadConfig() config {
	c := config{
		clientID:        mustEnv("CLIENT_ID"),
		clientSecret:    mustEnv("CLIENT_SECRET"),
		keycloakURL:     mustEnv("KEYCLOAK_URL"),
		federationID:    mustEnv("FEDERATION_ID"),
		domainName:      mustEnv("DOMAIN_NAME"),
		workloadName:    mustEnv("WORKLOAD_NAME"),
		port:            mustEnv("PORT"),
		peersFile:       mustEnv("PEERS_FILE"),
		noIntrospection: os.Getenv("NO_INTROSPECTION") == "1",
	}
	if c.noIntrospection {
		fmt.Printf("workload %s: stateless JWT validation (no introspection)\n", c.workloadName)
	}
	return c
}

func mustEnv(k string) string {
	v := os.Getenv(k)
	if v == "" {
		fmt.Fprintf(os.Stderr, "missing env %s\n", k)
		os.Exit(1)
	}
	return v
}

// ---------- inbound: validate Bearer token ----------

func handleAPI(w http.ResponseWriter, r *http.Request) {
	auth := r.Header.Get("Authorization")
	if !strings.HasPrefix(auth, "Bearer ") {
		http.Error(w, "missing bearer", 401)
		return
	}
	raw := strings.TrimPrefix(auth, "Bearer ")
	if err := validateToken(raw); err != nil {
		http.Error(w, "invalid token: "+err.Error(), 401)
		return
	}
	w.WriteHeader(200)
	fmt.Fprintf(w, "ok from %s/%s\n", cfg.domainName, cfg.workloadName)
}

type introspectResp struct {
	Active bool `json:"active"`
}

func validateToken(raw string) error {
	if cfg.noIntrospection {
		return validateTokenStateless(raw)
	}
	introspectURL := fmt.Sprintf("%s/realms/%s/protocol/openid-connect/token/introspect",
		cfg.keycloakURL, cfg.domainName)
	form := url.Values{}
	form.Set("token", raw)
	form.Set("client_id", cfg.clientID)
	form.Set("client_secret", cfg.clientSecret)

	c := &http.Client{Timeout: 5 * time.Second}
	resp, err := c.PostForm(introspectURL, form)
	if err != nil {
		return fmt.Errorf("introspection request failed: %w", err)
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	if resp.StatusCode != 200 {
		return fmt.Errorf("introspection returned %d: %s", resp.StatusCode, string(body))
	}
	var ir introspectResp
	if err := json.Unmarshal(body, &ir); err != nil {
		return fmt.Errorf("introspection parse: %w", err)
	}
	if !ir.Active {
		return fmt.Errorf("token not active")
	}
	return nil
}

func validateTokenStateless(raw string) error {
	parts := strings.Split(raw, ".")
	if len(parts) != 3 {
		return fmt.Errorf("not a JWT")
	}
	payload, err := base64.RawURLEncoding.DecodeString(parts[1])
	if err != nil {
		return fmt.Errorf("decode payload: %w", err)
	}
	var claims struct {
		Exp int64 `json:"exp"`
	}
	if err := json.Unmarshal(payload, &claims); err != nil {
		return fmt.Errorf("parse claims: %w", err)
	}
	if time.Now().Unix() >= claims.Exp {
		return fmt.Errorf("token expired")
	}
	return nil
}

// ---------- outbound: drive cross-domain call ----------

type callReq struct {
	TargetDomain string `json:"target_domain"`
	TargetURL    string `json:"target_url"`
}

func handleCall(w http.ResponseWriter, r *http.Request) {
	var req callReq
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, err.Error(), 400)
		return
	}
	if req.TargetDomain == "" || req.TargetURL == "" {
		http.Error(w, "target_domain and target_url required", 400)
		return
	}
	exKey := req.TargetDomain + "|" + req.TargetURL

	for attempt := 0; attempt < 2; attempt++ {
		tok, status, err := getOwnToken()
		if err != nil {
			if attempt == 0 && isAuthFailure(status) {
				invalidateOwnToken()
				continue
			}
			http.Error(w, "own token: "+err.Error(), 502)
			return
		}
		exTok, status, err := getExchangedToken(req.TargetDomain, req.TargetURL, tok)
		if err != nil {
			if attempt == 0 && isAuthFailure(status) {
				invalidateOwnToken()
				invalidateExchange(exKey)
				continue
			}
			http.Error(w, "exchange: "+err.Error(), 502)
			return
		}
		pstatus, body, err := callPeer(req.TargetURL, exTok)
		if err != nil {
			http.Error(w, "peer call: "+err.Error(), 502)
			return
		}
		if pstatus == 401 && attempt == 0 {
			invalidateExchange(exKey)
			continue
		}
		if pstatus != 200 {
			http.Error(w, fmt.Sprintf("peer returned %d: %s", pstatus, body), 502)
			return
		}
		w.WriteHeader(200)
		fmt.Fprintf(w, "%s\n", body)
		return
	}
	http.Error(w, "exhausted retries", 502)
}

func isAuthFailure(status int) bool {
	return status == 400 || status == 401
}

func invalidateOwnToken() {
	ownTokenMu.Lock()
	ownToken = nil
	ownTokenMu.Unlock()
}

func invalidateExchange(key string) {
	exchangeMu.Lock()
	delete(exchange, key)
	exchangeMu.Unlock()
}

func getOwnToken() (string, int, error) {
	ownTokenMu.Lock()
	defer ownTokenMu.Unlock()
	if ownToken != nil && time.Now().Before(ownToken.expiresAt.Add(-5*time.Second)) {
		return ownToken.value, 200, nil
	}
	tokURL := fmt.Sprintf("%s/realms/%s/protocol/openid-connect/token", cfg.keycloakURL, cfg.domainName)
	form := url.Values{}
	form.Set("grant_type", "client_credentials")
	form.Set("client_id", cfg.clientID)
	form.Set("client_secret", cfg.clientSecret)
	tr, status, err := postForm(tokURL, form)
	if err != nil {
		return "", status, err
	}
	ownToken = &cachedToken{value: tr.AccessToken, expiresAt: time.Now().Add(time.Duration(tr.ExpiresIn) * time.Second)}
	return ownToken.value, 200, nil
}

func getExchangedToken(targetDomain, targetURL, subjectToken string) (string, int, error) {
	key := targetDomain + "|" + targetURL
	exchangeMu.Lock()
	if t, ok := exchange[key]; ok && time.Now().Before(t.expiresAt.Add(-5*time.Second)) {
		exchangeMu.Unlock()
		return t.value, 200, nil
	}
	exchangeMu.Unlock()

	targetKC, err := lookupKeycloakURL(targetDomain)
	if err != nil {
		return "", 0, err
	}
	tokURL := fmt.Sprintf("%s/realms/%s/protocol/openid-connect/token", targetKC, targetDomain)
	clientID := fmt.Sprintf("%s-%s", cfg.federationID, cfg.domainName)
	subjectIssuer := clientID

	form := url.Values{}
	form.Set("grant_type", "urn:ietf:params:oauth:grant-type:token-exchange")
	form.Set("client_id", clientID)
	form.Set("subject_token", subjectToken)
	form.Set("subject_token_type", "urn:ietf:params:oauth:token-type:jwt")
	form.Set("subject_issuer", subjectIssuer)

	tr, status, err := postForm(tokURL, form)
	if err != nil {
		return "", status, err
	}
	exchangeMu.Lock()
	exchange[key] = &cachedToken{value: tr.AccessToken, expiresAt: time.Now().Add(time.Duration(tr.ExpiresIn) * time.Second)}
	exchangeMu.Unlock()
	return tr.AccessToken, 200, nil
}

func callPeer(targetURL, token string) (int, string, error) {
	req, err := http.NewRequest("GET", targetURL+"/api", nil)
	if err != nil {
		return 0, "", err
	}
	req.Header.Set("Authorization", "Bearer "+token)
	c := &http.Client{Timeout: 5 * time.Second}
	resp, err := c.Do(req)
	if err != nil {
		return 0, "", err
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	return resp.StatusCode, string(body), nil
}

func lookupKeycloakURL(domain string) (string, error) {
	metaMu.Lock()
	if u, ok := metaCache[domain]; ok {
		metaMu.Unlock()
		return u, nil
	}
	metaMu.Unlock()

	// Read from local peers file written by listener
	data, err := os.ReadFile(cfg.peersFile)
	if err != nil {
		return "", err
	}
	var peers map[string]string
	if err := json.Unmarshal(data, &peers); err != nil {
		return "", err
	}
	metaMu.Lock()
	defer metaMu.Unlock()
	for d, url := range peers {
		metaCache[d] = url
	}
	if u, ok := metaCache[domain]; ok {
		return u, nil
	}
	return "", fmt.Errorf("domain %s not in peers file", domain)
}

func postForm(u string, form url.Values) (*tokenResp, int, error) {
	resp, err := http.PostForm(u, form)
	if err != nil {
		return nil, 0, err
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	if resp.StatusCode != 200 {
		return nil, resp.StatusCode, fmt.Errorf("status %d: %s", resp.StatusCode, string(body))
	}
	var tr tokenResp
	if err := json.Unmarshal(body, &tr); err != nil {
		return nil, resp.StatusCode, err
	}
	return &tr, resp.StatusCode, nil
}
