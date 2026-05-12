# OIDC Workload Identity Federation Plan

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

## What OIDC Adds Over Plain OAuth 2.0

In the M2M context the practical difference is narrow:

- **Plain OAuth 2.0** (client credentials): issues an access token scoped for authorization ("you may call X"). The `sub` is an identifier but carries no standardized identity semantics.
- **OIDC infrastructure**: standardizes the issuer model, discovery endpoint, and JWT claims in a way that makes the token explicitly an **identity assertion** ("I am workload X") rather than just an authorization grant. The `sub` claim, issuer metadata, and JWKS endpoint are all governed by a well-known spec that relying parties can implement generically.

For federation purposes the OIDC discovery mechanism (`/.well-known/openid-configuration` → `jwks_uri`) is the key contribution: any party knowing an issuer URL can find its public keys without out-of-band configuration.

---

## Differences Between OIDC Direct Federation and OAuth Token Exchange

| | OIDC Direct Federation | OAuth + Token Exchange |
|---|---|---|
| W2 trusts | Domain 1's issuer directly | Its own domain's STS only |
| Who fetches foreign JWKS | W2 itself | Domain 2's STS |
| Runtime hops | W1 → own issuer → W2 | W1 → own issuer → D2 STS → W2 |
| Token W2 sees | Issued by D1 issuer | Issued by D2 STS |
| Cross-domain policy enforcement | Distributed at each workload | Centralized at STS |
| Complexity | Lower | Higher (extra STS component) |

---

## Difference Between OAuth/OIDC and SPIFFE

The fundamental distinction is **secret-based vs attestation-based identity**:

- OAuth/OIDC: W1 proves its identity to its issuer using a **client secret** it knows. The secret must be stored somewhere, distributed at deploy time, and rotated manually.
- SPIFFE/SPIRE: W1 proves its identity by **where it is running** — the SPIRE agent on the node attests the workload's identity based on platform facts (process ID, Kubernetes pod attributes, etc.) and issues a short-lived X.509 SVID or JWT-SVID. No secret is stored in the workload.

SPIFFE also issues X.509 SVIDs enabling **mutual TLS (mTLS)** natively, so both sides of a connection are authenticated at the transport layer, not just the application layer.

---

## Technology Choice: Keycloak

Use **Keycloak** (https://www.keycloak.org) as the issuer for the OIDC workload identity federation implementation.

### Why Keycloak

**Single component handles both roles.** Keycloak acts as an OAuth 2.0 authorization server and an OIDC provider in the same instance. The same Keycloak instance can serve as both Domain 1's issuer and be trusted by Domain 2 workloads — reducing the number of moving parts in the prototype.

**Native OIDC support out of the box.** Keycloak is a full-featured OIDC provider with all required flows and endpoints implemented.

**Standard JWKS and discovery endpoints out of the box.** Keycloak exposes `/.well-known/openid-configuration` and `/.well-known/jwks.json` without any custom code. These are the endpoints W2 needs to fetch and cache public keys.

**Client credentials grant supported natively.** Keycloak service accounts implement the client credentials flow — create a client, enable service account, call `/protocol/openid-connect/token` with `grant_type=client_credentials`. No extra configuration.

**Containerized and self-contained.** Keycloak runs as a single Docker container (`quay.io/keycloak/keycloak`), making it straightforward to spin up isolated instances representing different domains in a local prototype environment.

**Well-documented and widely used.** Extensive documentation and community support reduce implementation time. Comparable to what production environments use (Auth0, Okta, GCP IAM all implement the same standards).

### Suggested Deployment

Run Keycloak instances in Docker:
- `keycloak-d1`: Domain 1 issuer. Has a service account client for W1.
- W2 is configured to trust `keycloak-d1`'s JWKS endpoint directly, bypassing any STS.

This Docker Compose setup supports OIDC direct federation with configuration only, keeping the implementation clean.
