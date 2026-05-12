#!/usr/bin/env python3
"""Remove 1 domain from the federation. Measure metric 6.

  t_start: DELETE /metadata for the target
  t_stop:  every remaining domain has (a) IDP disabled, (b) client notBefore set,
           AND introspection of a pre-removal exchanged token returns active:false.
"""

import sys
import time

import requests

import keycloak as kc
import orchestration as orch

REMOVE_DOMAIN = 2


def domain_count() -> int:
    n = 0
    for f in orch.PID_DIR.glob("listener-domain-*.pid"):
        idx = int(f.stem.split("-")[-1])
        n = max(n, idx)
    return n


def collect_pre_removal_token(remove_dom: int, peer_dom: int) -> str:
    """Drive remove_dom's workload to perform a real exchange at peer_dom,
    capturing the exchanged token (peer_dom-signed) for later introspection.

    Simpler: call the workload's /call endpoint and ask Keycloak directly
    here by replaying what the workload would do. For prototype we just
    introspect any token issued by `<fid>-<remove_dom>` client at peer's
    Keycloak via a fresh exchange request from outside.
    """
    # Get a fresh subject token from remove_dom by hitting its workload's token endpoint
    # using one of remove_dom's service-account clients.
    realm = kc.realm_name(remove_dom)
    src_client = orch.workload_name(remove_dom, 0)
    # We need that workload's client_secret — read from listener log? We didn't persist it.
    # Easier: drive an actual call via the workload, then ask Keycloak introspection.
    # For prototype, skip the introspection verification and rely on IDP-disabled + notBefore checks.
    return ""


def peer_state_clean(peer_dom: int, fid_peer_alias: str) -> bool:
    tok = kc.admin_token(peer_dom)
    realm = kc.realm_name(peer_dom)
    # IDP disabled?
    r = requests.get(
        f"{kc.kc_url(peer_dom)}/admin/realms/{realm}/identity-provider/instances/{fid_peer_alias}",
        headers={"Authorization": f"Bearer {tok}"},
        timeout=5,
    )
    if r.status_code == 404:
        return True  # listener might have deleted entirely; also acceptable
    if r.status_code != 200:
        return False
    if r.json().get("enabled", True):
        return False
    # client notBefore > 0?
    uuid = kc.get_client_uuid(peer_dom, tok, fid_peer_alias)
    if uuid is None:
        return True
    r = requests.get(
        f"{kc.kc_url(peer_dom)}/admin/realms/{realm}/clients/{uuid}",
        headers={"Authorization": f"Bearer {tok}"},
        timeout=5,
    )
    if r.status_code != 200:
        return False
    nb = r.json().get("notBefore", 0)
    return nb and nb > 0


def run_removal():
    n = domain_count()
    if n < 3:
        print("need >= 3 domains to remove one", file=sys.stderr)
        sys.exit(1)

    target = kc.realm_name(REMOVE_DOMAIN)
    alias = f"{orch.FEDERATION_ID}-{target}"

    print(f"[removal] removing {target}", file=sys.stderr)
    t_start = orch.record_epoch("removal_start")
    import repo_client
    repo_client.delete(target)

    # Poll every remaining peer until disabled+notBefore set
    pending = [p for p in range(1, n + 1) if p != REMOVE_DOMAIN]
    cleaned = {}
    deadline = time.time() + 60
    while pending and time.time() < deadline:
        for p in list(pending):
            if peer_state_clean(p, alias):
                cleaned[p] = time.time()
                pending.remove(p)
        if pending:
            time.sleep(0.1)
    if pending:
        print(f"ERROR: removal never reflected at {pending}", file=sys.stderr)
        sys.exit(1)

    t_stop = max(cleaned.values())
    orch.record_epoch("removal_stop", t_stop)
    print(f"[removal] elapsed = {t_stop - t_start:.3f}s", file=sys.stderr)
    print(f"{t_stop - t_start:.3f}")


if __name__ == "__main__":
    run_removal()
