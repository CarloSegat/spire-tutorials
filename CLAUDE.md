# paper prototype
this project build a prototype that accompanies a paper.
The prototype represents the implementation of the paper and its goal is to provide the EVALUATION.
the purpose of the paper is to compare different technologies that can be used
to build federations of service providers/ identity providers.
e.g. a federation of hospitals and doctors that provide specialized ML inference,
e.g. a federation of MNO that agree on certain roaming requirements,
e.g. a federation/association of private individuals that agreed to pool hardware to build a shared cloud infra.
The specific use cases don't matter, the goal of the paper is to show how DLT
(distributed kedger technologies) can help.

# 3 technologies
- **SPIFFE/SPIRE**
- **OAuth 2.0** with token exchange (RFC 8693)
- **OIDC** workload identity federation (OIDC infrastructure reused for M2M)

# EVALUATION - quantitative
- time it takes to create a  federation (x = federation size, y = timein secodns); from posting of the first bundle (for SPIFFE), till full-mesh communication is achieved
- time it takes to add 1 memeber to an existing federation ((x = federation size, y = time in secodns); from posting of the new memeber bundle (for SPIFFE), till full-mesh communication is achieved
- time it takes to rotate a key for 1 member (just y = time in seconds)
- time after rotation, until the rotated key is propagated
- time it takes after propagation, to achieve full-mesh communication (i.e. all workloads across all clusters talked to each others)
- time it takes to remove 1 member from the federation (propagation)
- time it takes after removal to reach "zero communication" for the removed workloads

# Smart contract storage — future improvements
Both SPIFFE and OAuth ledger contracts currently store opaque JSON strings on-chain for simplicity. This is gas-inefficient. Future improvement: store only the endpoint URL on-chain (SPIRE bundle endpoint for SPIFFE, JWKS/metadata endpoint for OAuth) and let peers fetch the actual data off-chain. For SPIFFE specifically, storing only the SPIRE bundle endpoint URL means key rotation is no longer a ledger operation — the URL stays the same, only the content behind it changes. This is the pattern OAuth already uses naturally (Keycloak rotates keys internally, peers re-fetch from the same JWKS endpoint).

# OAuth key rotation measurement — current limitation
OAuth-only (SPIFFE rotation is handled natively by SPIRE via bundle endpoints/ledger updates). The OAuth rotation propagation metric (metric 4) is artificial: the orchestration script directly calls each peer's Keycloak admin API (`reload-keys`) to force JWKS re-fetch, rather than peers discovering the rotation autonomously. No domain-to-domain signaling occurs — the test harness acts as a god-view puppet master. This is identical in both OAuth centralized and OAuth ledger variants. Future improvement: implement push-based notification of rotation — SSE events for centralized, contract events for ledger — so peers re-fetch JWKS upon notification rather than being force-reloaded by the orchestrator. In the paper discussion, note that in production propagation depends on the JWKS cache refresh rate (tied to TTL), but a push mechanism can be implemented and the prototype measures this push-based approach.
