# OAuth 2.0 Token Exchange Plan

## How OAuth 2.0 Works in This Context

OAuth 2.0 is an authorization framework.
In the M2M/workload context the relevant grant is **client credentials** (RFC 6749 §4.4): a workload authenticates to its own issuer using a client ID and secret and receives a short-lived access token (JWT). No human is involved.

For cross-domain federation, **token exchange** (RFC 8693) is layered on top:

1. **Setup (once at deploy time):** Domain 2's STS fetches Domain 1 issuer's public keys from `/.well-known/jwks.json` and caches them. W2 separately fetches Domain 2 STS's public keys.
2. **Runtime (every request):**
   - W1 calls its own issuer with client credentials → receives a JWT signed by Domain 1.
   - W1 presents that JWT to Domain 2's STS with grant type `urn:ietf:params:oauth:grant-type:token-exchange`.
   - Domain 2's STS validates the incoming JWT against cached Domain 1 keys, then issues a **new JWT** signed by itself, scoped to W2 as audience.
   - W1 calls W2 with `Authorization: Bearer <new-jwt>`.
   - W2 validates the token against Domain 2 STS's cached public keys — W2 never contacts Domain 1 directly.

**Key properties:**
- W2's trust boundary is entirely local: it only trusts its own domain's STS.
- The cross-domain key fetching is the STS's responsibility, not W2's.
- The STS can scope down claims, change audience, and enforce cross-domain policy centrally.
- Credentials are secret-based: W1 authenticates to its issuer using a client secret that must be stored and rotated.

---

## Comparison

**OAuth Token Exchange vs OIDC Direct Federation:**

| | OAuth + Token Exchange | OIDC Direct Federation |
|---|---|---|
| W2 trusts | Its own domain's STS only | Domain 1's issuer directly |
| Who fetches foreign JWKS | Domain 2's STS | W2 itself |
| Runtime hops | W1 → own issuer → D2 STS → W2 | W1 → own issuer → W2 |
| Token W2 sees | Issued by D2 STS | Issued by D1 issuer |
| Cross-domain policy enforcement | Centralized at STS | Distributed at each workload |
| Complexity | Higher (extra STS component) | Lower |

**OAuth/OIDC vs SPIFFE — secret-based vs attestation-based identity:**

- OAuth/OIDC: W1 proves its identity to its issuer using a **client secret** it knows. The secret must be stored somewhere, distributed at deploy time, and rotated manually.
- SPIFFE/SPIRE: W1 proves its identity by **where it is running** — the SPIRE agent on the node attests the workload's identity based on platform facts (process ID, Kubernetes pod attributes, etc.) and issues a short-lived X.509 SVID or JWT-SVID. No secret is stored in the workload.

SPIFFE also issues X.509 SVIDs enabling **mutual TLS (mTLS)** natively, so both sides of a connection are authenticated at the transport layer, not just the application layer.

---

## Technology Choice: Keycloak

**Note:** In this plan, "STS" (Security Token Service) and "issuer" refer to the same entity — the Keycloak instance responsible for minting and validating tokens.

Use **Keycloak** (https://www.keycloak.org) as the issuer/STS for the OAuth token exchange implementation.

### Why Keycloak

Keycloak provides every piece needed out of the box: RFC 8693 token exchange, client-credentials grant via service accounts, standard `/.well-known/openid-configuration` and JWKS endpoints, and built-in "Identity Provider" objects to register foreign JWKS URIs — no custom code. It runs as a single container (`quay.io/keycloak/keycloak`), so N isolated domains are trivial to spin up. It is widely deployed and behaves like the production-grade equivalents (Auth0, Okta, GCP IAM) that implement the same standards.

---

## Core Concepts

**JWKS (JSON Web Key Set):** A JSON document containing public keys in JWK format (RFC 7517). In this context:
- Each Keycloak instance exposes its public keys at `/.well-known/jwks.json`
- This URL is the JWKS endpoint
- Other domains fetch this endpoint to get the keys needed to validate tokens

**Federation Metadata Repository:** Stores the federation's membership:
- Domain name
- Keycloak instance endpoint URL
- JWKS URL (where to fetch that domain's public keys)
- Timestamp

**Metadata repo role:** Discovery for orchestration layer only. NOT queried by Keycloak at token-exchange time. Each domain self-registers its own metadata. A listener process on each domain watches the repo, detects new entries, and calls that domain's own Keycloak admin API to register peer IDPs. Mirrors SPIFFE's listen_and_react pattern.

**Per-Peer Exchange Clients (federation-scoped):** Each Keycloak realm has one public (no-secret) exchange client *per registered foreign peer*, named `<federation_id>-<source_domain_name>`. The IDP alias used to validate that peer's subject_token uses the same name. Per-peer granularity is required to revoke in-flight tokens on removal (see "Zero Communication for Removal"); Keycloak does **not** cascade IDP disable to already-issued exchanged tokens, so we need a client-scoped `notBefore` lever per peer. Security still comes from subject_token signature validation; the client is public because the prototype is single-tenant.

---

## OAuth Token Exchange Deployment Models

To evaluate OAuth token exchange against SPIFFE/SPIRE, build two deployment topologies:

### 1. Centralized OAuth (Mirroring centralized-spiffe)

**Architecture:**
- Each domain runs its own Keycloak instance (STS)
- All domains self-register their JWKS URLs in a **centralized metadata repository** (HTTP-based)
- Each domain runs a listener process watching the repo for new entries
- At runtime:
  - W1 authenticates to its own domain's Keycloak (client credentials) → gets D1-signed access token
  - W1 calls Domain 2's Keycloak token exchange endpoint with the D1 token
  - D2's Keycloak validates D1 token against cached D1 JWKS (pre-registered by D2's listener) → issues D2-signed exchange token
  - W1 calls W2's HTTP endpoint with Bearer token (D2-signed)
  - W2 validates token against cached D2 JWKS → returns 200

**Setup:**
- Deploy N Keycloak instances (one per domain)
- Deploy a centralized metadata repository (HTTP endpoint, in-memory store, same as centralized-spiffe):
  - GET `/metadata?federation_id=<fid>` → list all domains in federation `<fid>` with their JWKS URLs and Keycloak endpoints
  - POST `/metadata/register?federation_id=<fid>` → domain self-registers its own metadata into federation `<fid>`
  - Multiple federations coexist in the same repo, scoped by `federation_id` (same model as centralized-spiffe)
- Each domain runs one Keycloak instance + one listener process (mirrors listen_and_react.py)
  - Listener watches repo for new entries
  - On new entry: calls local Keycloak admin API to register new IDP
  - Each listener only configures its own local Keycloak, never touches other domains' Keycloaks

---

### 2. Ledger-Based OAuth (Mirroring ledger-spiffe)

**Architecture:**
- Each domain runs its own Keycloak instance (STS)
- All domains self-register their JWKS URLs on a **blockchain/ledger** (Ethereum smart contract)
- Each domain runs a listener process polling the ledger for new entries
- At runtime:
  - Same token exchange flow as Centralized OAuth (W1 → D1 token → D2 exchange → D2 token → W2)
  - D2's Keycloak has D1's JWKS URL pre-cached (set by D2's listener after detecting D1 on ledger)

**Setup:**
- Deploy N Keycloak instances (one per domain)
- Deploy Ethereum smart contract (or equivalent ledger) that stores:
  - Domain name
  - Keycloak endpoint URL
  - JWKS URL (the `/.well-known/jwks.json` endpoint)
  - Timestamp
- Each domain self-posts its metadata transaction to the ledger
- Each domain runs one listener process:
  - Polls ledger for new entries (vs. SSE push for centralized)
  - On new entry: calls local Keycloak admin API to register peer IDP
  - Same pattern as centralized: listener only touches own Keycloak

---

## Architectural Details

### Keycloak Realm Configuration

Each domain's Keycloak setup includes:

1. **Realm:** `domain-N`
2. **Service account clients (4 per domain):** `workload-N-{0,1,2,3}` with client credentials grant enabled
3. **Per-peer exchange clients:** one public (no-secret, confidential=false) client per registered foreign peer, named `<federation_id>-<source_domain_name>` (e.g. `fed1-domain-1`)
   - Created/destroyed by the local listener in lockstep with the matching IDP alias of the same name
   - Used by source-domain workloads to call this realm's token exchange endpoint
   - On peer removal: listener disables the IDP **and** sets `notBefore=now` on the matching client → hard-stop revocation (see "Zero Communication for Removal")
   - Security relies on subject_token signature validation, not client secrecy

### Workload Identity & Credentials

- Each workload holds: own domain's `client_id` + `client_secret` (set at deploy time), plus knows its own `federation_id` and `domain_name`
- No per-target-domain secrets needed (enabled by public per-peer exchange clients)
- W1 derives target domain's Keycloak URL from federation metadata at runtime
- W1 calls D2's `/token` with `client_id=<federation_id>-<own_domain_name>` (the exchange client D2's listener created for D1)

### Domain Self-Registration & IDP Setup

**Self-registration (domain posts its own metadata only):**
- Domain N script posts to repo/ledger: its own JWKS URI + Keycloak endpoint URL
- Nobody posts on behalf of another domain

**Reactive listener (per-domain IDP + client registration):**
- Each domain runs a listener watching the metadata repo/ledger for membership events scoped by `federation_id`
  - **Centralized variant:** listener uses SSE (server-sent events) push from HTTP repo — instant detection
  - **Ledger variant:** listener polls blockchain (configurable interval, ~1s) — introduces poll latency
- On *add* event for peer K in federation F: listener calls ITS OWN Keycloak admin API to create two objects, both named `F-K`:
  1. IDP alias `F-K`: `POST /admin/realms/domain-N/identity-provider/instances` with K's JWKS URI as `jwksUrl`
  2. Public exchange client `F-K`: `POST /admin/realms/domain-N/clients` with `publicClient=true`, token-exchange permissions enabled, allowed for subject_issuer = IDP `F-K`
- On *remove* event for peer K in federation F: listener performs the revocation pair (see "Zero Communication for Removal" item 2)
- Listener only ever configures its own local Keycloak
- O(n²) total `(IDP, client)` pairs across the federation; each domain makes O(n) local calls

### Token Exchange at Runtime

```
W1 → D1's Keycloak: client_credentials grant
     ↓ D1-signed access token
W1 → D2's Keycloak: token exchange (client_id=<federation_id>-<D1_domain_name>, subject_token=D1 token)
     ↓ D2-signed exchange token (issued by client <fid>-<D1>, audience=W2)
W1 → W2: Bearer token (D2 token)
     ↓ W2 validates against cached D2 JWKS (or introspects at D2 STS — see Zero Communication)
W2 → 200 OK
```

### Key Rotation & Propagation

**Keycloak key rotation:**
1. Call Keycloak admin: generate new RSA key pair, set as active signing key
2. New tokens from D1's Keycloak are signed with the new key
3. D1's JWKS endpoint immediately serves the new key

**Propagation to peers (pull-triggered, not push):**
- Other domains' Keycloaks have cached D1's old JWKS via the IDP registration
- First token exchange attempt at a peer with a new-key-signed subject_token → cached JWKS lacks the new `kid` → Keycloak's `PublicKeyStorageManager` refetches D1's JWKS → validation succeeds
- Rate-limit: `minTimeBetweenJwksRequests` (default 10ms per JWKS URL) — negligible vs HTTP RTT
- Separate TTL: `publicKeyCacheTtl` forces refresh even for known kids (default ~24h, irrelevant for rotation propagation)
- Propagation is **lazy/on-demand**, unlike SPIFFE's push-via-SSE — a peer that never receives a new-key-signed token will keep the stale JWKS forever (or until `publicKeyCacheTtl`)
- For metric 4, the orchestrator must explicitly trigger a token exchange at each peer post-rotation to force the refetch; otherwise propagation is unbounded

### Zero Communication for Removal

Two mechanisms, both implemented:

1. **Token TTL expiry (configurable per experiment):**
   - Set Keycloak access token TTL (e.g., 30s, 60s, 120s)
   - Removal: deregister domain from repo → workloads' tokens expire → communication dies
   - Deterministic but introduces artificial latency floor

2. **Introspection at W2 + per-peer `notBefore` (hard-stop):**
   - W2 calls Keycloak introspection endpoint on each incoming request
   - **Why the per-peer client matters:** Keycloak does NOT cascade IDP-disable to invalidate already-issued exchanged tokens (verified: docs state *"the revocation of the access-token1 will not revoke access-token2"*). Disabling the IDP alone only blocks future exchanges; in-flight tokens stay valid till TTL. To force `active:false` on introspection, the issuing client's `notBefore` must be bumped past the token's `iat`.
   - **Removal procedure for peer K of federation F at this domain:**
     1. `PUT /admin/realms/{r}/identity-provider/instances/F-K` set `enabled=false` (blocks new exchanges)
     2. `PUT /admin/realms/{r}/clients/{F-K-id}` set `notBefore=<now epoch seconds>` (invalidates in-flight tokens issued by client `F-K`)
   - Next W2 introspection of any such token → `{"active": false}` → 401
   - Multi-federation isolation: only client `F-K` is bumped; K's clients in other federations untouched
   - Adds per-request latency at W2 (+1 local RTT to D2 STS)

   **Flow:**
   1. W1 (D1) → D1 STS: client_credentials → D1-signed token
   2. W1 → D2 STS: token exchange → D2-signed token (audience=W2)
   3. W1 → W2: Bearer D2-token
   4. W2 → D2 STS (its own, local domain) `/introspect` → active?

   Cost: +1 local RTT per inbound cross-domain request. LAN/loopback fast, but still serialized in critical path.

**Paper note:** In production, use introspection + confidential (secret-required) per-peer exchange clients for defense-in-depth. Public client is acceptable for prototype timing measurements.

---

## Quantitative Evaluation Metrics

All times measured in seconds using monotonic clock on the orchestrator host. All workloads run 4 service-account clients (`workload-N-{0,1,2,3}`). "Successful call" = HTTP 200 from W_target after full token exchange flow (W_src obtains D_src token → exchanges at D_tgt Keycloak → calls W_tgt with Bearer). "Full-mesh" = every workload in every domain has made one successful call to every workload in every other domain (4×4×N×(N−1) ordered pairs total).

For both OAuth models, measure:

1. **Federation creation time** (y=seconds, x=N domains, N ∈ {2,4,8,16})
   - **t_start:** orchestrator issues first `POST /metadata/register` (centralized) or first ledger submit-tx (ledger), for domain 1
   - **t_stop:** orchestrator observes last successful cross-domain call completing the full-mesh matrix
   - Assumes N Keycloak instances already running and healthy; excludes Keycloak container boot time

2. **Member addition time** (y=seconds, x=existing federation size N, N ∈ {2,4,8,16}; exactly 1 domain added per trial)
   - Pre-state: N-domain federation at full-mesh; new domain N+1's Keycloak already running and healthy
   - **t_start:** orchestrator issues `POST /metadata/register` (or ledger submit-tx) for domain N+1
   - **t_stop:** orchestrator observes the last successful call completing full-mesh between domain N+1 and all existing N domains (bidirectional: 4×4×2×N ordered pairs)

3. **Key rotation time** (y=seconds, single value per run, fixed N=8)
   - **t_start:** orchestrator issues `POST /admin/realms/domain-1/keys` to generate+activate new RSA key on D1 Keycloak
   - **t_stop:** D1 Keycloak admin API returns 2xx confirming new key is active signing key
   - Measures only the rotation operation itself, not propagation

4. **Key propagation latency** (y=seconds, fixed N=8)
   - **t_start:** same as metric 3's t_stop (new key active on D1)
   - **t_stop:** all N−1 peer Keycloaks' cached D1 JWKS contain the new key's `kid` (verified by orchestrator polling each peer's `/admin/realms/domain-N/identity-provider/instances/domain-1` keys endpoint at 100ms interval)
   - Note: propagation is pull-triggered, so first measurement requires triggering a token exchange at each peer to force JWKS refresh

5. **Post-rotation full-mesh time** (y=seconds, fixed N=8)
   - **t_start:** same as metric 4's t_stop (new key cached at all peers)
   - **t_stop:** orchestrator observes full-mesh successful-call matrix re-established using tokens signed by the new key (verified by inspecting `kid` header of D1-signed subject tokens)

6. **Member removal time** (y=seconds, x=federation size N before removal, N ∈ {2,4,8,16}; exactly 1 domain removed per trial)
   - Pre-state: N-domain federation at full-mesh; each remaining domain holds at least one in-flight D2-token exchanged from the to-be-removed domain X
   - **t_start:** orchestrator issues `DELETE /metadata/{domain-X}` (centralized) or ledger remove-tx (ledger) for the target domain
   - **t_stop:** all N−1 remaining domains' Keycloaks have (a) IDP `<fid>-X` disabled AND (b) client `<fid>-X` `notBefore` set, AND introspection of a pre-removal token issued by client `<fid>-X` returns `{"active": false}` (verified by orchestrator polling each remaining Keycloak at 100ms interval)
   - Without the per-peer `notBefore` bump, introspection would still return `active:true` and the metric would collapse to TTL — both listener steps are required for the hard-stop semantics
   - Token TTL expiry path measured separately as `(configured TTL) + ε`; not reported as a primary metric since it is deterministic by configuration

---

## Comparison: Centralized vs Ledger-Based OAuth

| Aspect | Centralized OAuth | Ledger-Based OAuth |
|---|---|---|
| STS instances | N (one per domain) | N (one per domain) |
| Metadata repository | Centralized HTTP DB | Blockchain/ledger |
| Metadata availability | Single point of failure; outage blocks listener → blocks new IDP registrations (not runtime token exchange) | Distributed; decentralized; ledger outage blocks listener |
| Listener mechanism | SSE push from repo | Polling ledger (configurable interval) |
| Key rotation propagation | Pull-triggered on validation failure (same as ledger) | Pull-triggered on validation failure (same as centralized) |
| Token exchange latency | Unaffected by repo latency (Keycloak uses pre-cached IDP, not runtime lookup) | Unaffected by ledger latency (same reason) |
| IDP registration latency | Listener detection + admin API call time | Listener poll interval + admin API call time |
| Implementation complexity | Lower (standard HTTP API) | Higher (blockchain integration, smart contract) |
| Federation bootstrap cost | Deploy repo + N domains, each self-registers | Deploy ledger + N domains, each self-registers |
| Operational cost | Repo downtime prevents new member joins | Ledger downtime prevents new member joins; polling introduces delay |

---

## Implementation Decisions

### Keycloak deployment
- **One Keycloak instance per domain**, one realm `domain-N` per instance. No multi-realm sharing — domain boundary = process boundary.
- **Run native, not Docker.** Mirrors SPIRE process orchestration. Download `keycloak-26.x.tar.gz` once into `artefacts/keycloak/`. Per-domain launch: `bin/kc.sh start-dev --http-port=<8081+i> --hostname-strict=false` with isolated `KC_HOME=<data-dir-i>`. Spawned by orchestrator via `subprocess.Popen`, same pattern as `start_centralized_spiffe_binary()`. Requires JDK 17+ on host.
- **Storage:** embedded H2 in dev mode. No persistence across runs. Reset = kill process + wipe data dir.
- **Admin auth:** master realm `admin/admin` (Keycloak dev-mode default via `KEYCLOAK_ADMIN`/`KEYCLOAK_ADMIN_PASSWORD` env). Listener's first admin call after boot: `PUT /admin/realms/master` setting `accessTokenLifespan=86400` so listener holds one admin token for the whole experiment — no refresh logic, no 401 retry.

### Workloads
- **Language:** Go (mirrors `centralized-db/main.go` Go infra; native HTTP server, `jwx/v2/jwk` for validation).
- **HTTP server:** each workload binds a distinct port, exposes one endpoint returning 200 on Bearer-token success.
- **Token validation at W2:** lazy JWKS fetch via `keyfunc`/`jwx` — cache populated on first unknown `kid`, refetch on cache miss. No startup readiness barrier.
- **Exchanged-token cache at W1:** keyed by `(target_domain, target_workload)`, reused until expiry. `audience` claim scoped per-target-workload.
- **Service-account credentials:** orchestrator creates the 4 `workload-N-{0,1,2,3}` clients via admin API after Keycloak `/health/ready` passes, reads back each `client_secret`, then `subprocess.Popen` the workload with env `CLIENT_ID`, `CLIENT_SECRET`, `KEYCLOAK_URL`, `FEDERATION_ID`, `DOMAIN_NAME`. No files, no realm-export JSON.

### Metadata repository (centralized variant)
- **Reuse existing `centralized-db` Go service.** Extend with **parallel** endpoints alongside `/bundle` — do NOT polymorphize the bundle type.
  - `POST /metadata/register?federation_id=<fid>` — body `{DomainName, KeycloakURL, JWKSURL}`
  - `GET /metadata?federation_id=<fid>` — list
  - `DELETE /metadata?federation_id=<fid>&domain=<name>`
  - SSE channel shared with `/events`; OAuth metadata events tagged so listeners subscribe only to their tech.
- **SSE payload:** full record (`{event_type, domain_name, keycloak_url, jwks_url}`). No two-step event → GET pattern.

### Listener
- One Go (or Python — TBD, follow workload choice = Go) listener process per domain.
- Boots after own Keycloak is ready. Sequence: fetch admin token → bump master realm TTL → subscribe to repo SSE filtered to OAuth `/metadata` events for own `federation_id` → on each `add`/`remove` event, call local Keycloak admin API to create/destroy the `F-K` IDP + per-peer exchange client pair.
- Listener never touches non-local Keycloaks.

### Orchestrator & full-mesh driver
- **Parallelism:** all 4×4×N×(N−1) pairs fired concurrently with bounded in-flight limit (~100) to avoid socket exhaustion.
- **Retry cadence:** per-pair fixed 100ms retry until HTTP 200. Matches the 100ms poll cadence used by metrics 4 and 6. Quantization ±50ms.
- **t_stop detection:** orchestrator drives the calls directly and records wall-clock of last 200 received.


