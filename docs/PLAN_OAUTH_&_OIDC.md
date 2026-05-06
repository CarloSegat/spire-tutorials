# Prototype Plan: Federation Management Comparison

## Goal

Build a prototype that compares three workload identity federation approaches:

- **SPIFFE/SPIRE** (already implemented)
- **OAuth 2.0** with token exchange (RFC 8693)
- **OIDC** workload identity federation (OIDC infrastructure reused for M2M)

The scenario is: Workload 1 (W1) in Domain 1 authenticates and calls Workload 2 (W2) in Domain 2. The prototype must support setting up the federation between domains, adding members, and revoking members.

---

## How OAuth 2.0 Works in This Context

OAuth 2.0 is an authorization framework. In the M2M/workload context the relevant grant is **client credentials** (RFC 6749 §4.4): a workload authenticates to its own issuer using a client ID and secret and receives a short-lived access token (JWT). No human is involved.

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

## How OIDC Workload Federation Works in This Context

OIDC is not used here for its human-facing flows (authorization code, consent screens, ID tokens for users). What is reused is the **OIDC infrastructure**: JWT format with standard claims (`iss`, `sub`, `aud`, `exp`), issuer discovery via `/.well-known/openid-configuration`, and public key distribution via `/.well-known/jwks.json`.

In this mode the platform (Keycloak, GitHub Actions, GCP Workload Identity) issues short-lived JWTs directly to workloads asserting their identity. The `sub` claim identifies the workload, not a human user.

Cross-domain flow (direct federation, no STS hop):

1. **Setup (once at deploy time):** W2 fetches Domain 1 issuer's public keys from `/.well-known/jwks.json` and caches them. W2 trusts Domain 1's issuer directly.
2. **Runtime (every request):**
   - W1 requests a token from its issuer (client credentials or platform-issued token). The resulting JWT has `iss=domain1`, `sub=workload1`.
   - W1 calls W2 with `Authorization: Bearer <jwt>`.
   - W2 validates the JWT against the cached Domain 1 JWKS directly — no STS hop, no intermediate token swap.

**Key properties:**
- W2 trusts foreign issuers directly — its trust boundary spans domains.
- One fewer runtime hop than token exchange.
- The token W1 presents is the same token issued by Domain 1's issuer (not re-issued by a local STS).
- Still secret-based at the local authentication step (W1 → its issuer).

---

## Differences Between OAuth Token Exchange and OIDC Direct Federation

| | OAuth + Token Exchange | OIDC Direct Federation |
|---|---|---|
| W2 trusts | Its own domain's STS only | Domain 1's issuer directly |
| Who fetches foreign JWKS | Domain 2's STS | W2 itself |
| Runtime hops | W1 → own issuer → D2 STS → W2 | W1 → own issuer → W2 |
| Token W2 sees | Issued by D2 STS | Issued by D1 issuer |
| Cross-domain policy enforcement | Centralized at STS | Distributed at each workload |
| Complexity | Higher (extra STS component) | Lower |

Both approaches use access tokens (JWTs) in the `Authorization: Bearer` header for the final W1 → W2 call. Both rely on the same JWKS discovery and JWT validation machinery. The structural difference is whether W2 trusts foreign issuers directly or only its local STS.

---

## What OIDC Adds Over Plain OAuth 2.0

In the M2M context the practical difference is narrow:

- **Plain OAuth 2.0** (client credentials): issues an access token scoped for authorization ("you may call X"). The `sub` is an identifier but carries no standardized identity semantics.
- **OIDC infrastructure**: standardizes the issuer model, discovery endpoint, and JWT claims in a way that makes the token explicitly an **identity assertion** ("I am workload X") rather than just an authorization grant. The `sub` claim, issuer metadata, and JWKS endpoint are all governed by a well-known spec that relying parties can implement generically.

For federation purposes the OIDC discovery mechanism (`/.well-known/openid-configuration` → `jwks_uri`) is the key contribution: any party knowing an issuer URL can find its public keys without out-of-band configuration.

---

## Difference Between OAuth/OIDC and SPIFFE

The fundamental distinction is **secret-based vs attestation-based identity**:

- OAuth/OIDC: W1 proves its identity to its issuer using a **client secret** it knows. The secret must be stored somewhere, distributed at deploy time, and rotated manually.
- SPIFFE/SPIRE: W1 proves its identity by **where it is running** — the SPIRE agent on the node attests the workload's identity based on platform facts (process ID, Kubernetes pod attributes, etc.) and issues a short-lived X.509 SVID or JWT-SVID. No secret is stored in the workload.

SPIFFE also issues X.509 SVIDs enabling **mutual TLS (mTLS)** natively, so both sides of a connection are authenticated at the transport layer, not just the application layer.

---

## Technology Choice for OAuth and OIDC: Keycloak

Use **Keycloak** (https://www.keycloak.org) as the issuer/STS for both the OAuth token exchange and OIDC federation implementations.

### Why Keycloak

**Single component handles both roles.** Keycloak acts as an OAuth 2.0 authorization server and an OIDC provider in the same instance. The same Keycloak deployment can serve as Domain 1's issuer and Domain 2's STS — reducing the number of moving parts in the prototype.

**Native token exchange support.** Keycloak implements RFC 8693 token exchange. It can be configured to accept tokens from a foreign issuer (by registering the foreign JWKS endpoint) and issue a locally-signed token in exchange. This maps directly to the cross-domain token exchange flow.

**Standard JWKS and discovery endpoints out of the box.** Keycloak exposes `/.well-known/openid-configuration` and `/.well-known/jwks.json` without any custom code. These are the endpoints W2 (in OIDC direct federation) and the STS (in token exchange) need to fetch public keys.

**Client credentials grant supported natively.** Keycloak service accounts implement the client credentials flow — create a client, enable service account, call `/protocol/openid-connect/token` with `grant_type=client_credentials`. No extra configuration.

**Containerized and self-contained.** Keycloak runs as a single Docker container (`quay.io/keycloak/keycloak`), making it straightforward to spin up two isolated instances representing Domain 1 and Domain 2 in a local prototype environment.

**Identity providers / JWKS federation built in.** Keycloak has a built-in concept of "Identity Providers" that can be configured to trust a foreign issuer by pointing at its JWKS URI. This is the setup step for token exchange without custom code.

**Well-documented and widely used.** Extensive documentation and community support reduce implementation time. Comparable to what production environments use (Auth0, Okta, GCP IAM all implement the same standards).

### Suggested Deployment

Run two Keycloak instances in Docker:
- `keycloak-d1`: Domain 1 issuer. Has a service account client for W1.
- `keycloak-d2`: Domain 2 STS. Configured with an Identity Provider pointing at `keycloak-d1`'s JWKS endpoint. Has token exchange policies allowing D1 tokens to be exchanged for D2-scoped tokens.

For OIDC direct federation, W2 is configured to trust `keycloak-d1`'s JWKS endpoint directly, bypassing `keycloak-d2`.

This single Docker Compose setup supports both protocol variants with configuration changes only, keeping the comparison clean.
