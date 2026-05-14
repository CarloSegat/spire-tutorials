# OAuth revocation / introspection — problems hit

## Goal
Make member-removal in OAuth reach **zero communication** (matching SPIFFE's metric semantics). Receivers must reject (a) pre-removal cached tokens and (b) any new token-exchange attempts from the removed domain.

## Problems & fixes

### 1. Stale workload binary (introspection never ran)
- `introspectToken` in `oauth/workload/main.go` did `url := fmt.Sprintf(...)`, shadowing the imported `net/url` package, then called `url.QueryEscape(...)` on the shadowed string.
- Compile error → `go build` failed silently in the dev loop → running binary was a pre-introspection build.
- Symptom: zero `validateToken` / `introspect` log lines despite the code being present in source.
- Fix: rename local var to `endpoint`, build form with `url.Values{}`. Rebuild binary. Logs then showed `active=false → REJECTED` for cached tokens.

### 2. `disable_idp` does NOT block token-exchange
- Initial revocation strategy: disable IDP alias `fed1-<peer>` + bump client `notBefore`.
- Empirical result: post-removal, senders kept succeeding. Workload logs:
  `[workload-2-0] exchange OK for domain-X expires_in=300`
- Confirmed via direct curl probe (`/tmp/exch_probe.py`): token-exchange with `subject_issuer=fed1-<removed>` returned HTTP 200 at all peer Keycloaks even after IDP `enabled=false`.
- Conclusion: in Keycloak, IDP alias `enabled=false` is cosmetic for `subject_issuer=<alias>` token-exchange; it does not refuse the grant.
- Fix: add `kc.disable_client(fed1-<peer>)` (client `enabled=false`). This is the hard stop. `handle_remove` now does 3 things: `disable_idp` + `set_client_not_before` + `disable_client`.

### 3. Sender retry loop masked revocation
- `handleCall` on 401 → `invalidateExchange` → refetch token-exchange → re-call peer.
- Before fix #2: refetch succeeded (client still enabled) → sender bypassed introspection rejection. Probe never observed all-fail rounds.
- After fix #2: refetch fails (client disabled) → handleCall returns 502.

### 4. Round-based probe granularity → `zero_comm = 0.000s`
- Original probe: synchronous rounds (~1s) over all (src,tgt) pairs.
- Revocation completed inside an inter-round sleep → probe never saw any post-removal success → `last_success_round_ts < removal_start` → metric clamped to 0.
- Fix: rewrite `probe_zero_communication` in `orchestration.py` as continuous per-pair worker threads recording `last_success_ts`. Declare zero_comm when `now - last_success_ts >= quiet_window` AND `removal_start_ts` is set.
- Result: finite `0.355s`.

### 5. Probe load inflates `removal_s`
- Continuous 64-thread probing competes with admin polling (`peer_state_clean`) at Keycloak.
- `removal_s` rose from ~0.4s (round-based) to ~2s (continuous).
- Open: back off probe rate during removal polling, or accept the load as part of the measurement environment.

## Final revocation (3 actions per remaining peer, `listen_and_react.py:48-58`)
1. `disable_idp(fed1-<peer>)`
2. `set_client_not_before(fed1-<peer>, now)` — invalidates already-issued tokens via introspection
3. `disable_client(fed1-<peer>)` — refuses new token-exchange (the actual revocation)

Receiver enforcement: `validateToken` in `oauth/workload/main.go` introspects every inbound token. Sender path: `handleCall` retries on 401, refetch fails because client is disabled, returns 502.

## Latest run (N=4)
```
removal: 1.998s
zero_comm: 0.355s
```
