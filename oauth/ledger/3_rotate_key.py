#!/usr/bin/env python3
"""Rotate the signing key on domain-1 and measure:

  metric 3: time to rotate (admin call latency)
  metric 4: time until each peer empirically accepts a token signed
            with the new key (via a real token-exchange round-trip)
  metric 5: time to re-establish full-mesh with new-key-signed tokens
"""

import sys
import time

import requests

import keycloak as kc
import orchestration as orch
import repo_client

ROTATE_DOMAIN = 1


def get_current_kid(domain_index: int, tok: str = None) -> str:
    """Active RS256 kid for the realm (admin /keys → active map)."""
    if tok is None:
        tok = kc.admin_token(domain_index)
    realm = kc.realm_name(domain_index)
    url = f"{kc.kc_url(domain_index)}/admin/realms/{realm}/keys"
    r = requests.get(url, headers={"Authorization": f"Bearer {tok}"}, timeout=5)
    r.raise_for_status()
    return r.json().get("active", {}).get("RS256", "")


def mint_fresh_subject_token(domain_index: int, client_id: str, client_secret: str) -> str:
    realm = kc.realm_name(domain_index)
    url = f"{kc.kc_url(domain_index)}/realms/{realm}/protocol/openid-connect/token"
    r = requests.post(
        url,
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        },
        timeout=10,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def try_exchange_at_peer(peer_dom: int, alias: str, subject_token: str) -> int:
    realm = kc.realm_name(peer_dom)
    url = f"{kc.kc_url(peer_dom)}/realms/{realm}/protocol/openid-connect/token"
    r = requests.post(
        url,
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
            "client_id": alias,
            "subject_token": subject_token,
            "subject_token_type": "urn:ietf:params:oauth:token-type:jwt",
            "subject_issuer": alias,
        },
        timeout=10,
    )
    return r.status_code


def domain_count() -> int:
    n = 0
    for f in orch.PID_DIR.glob("listener-domain-*.pid"):
        idx = int(f.stem.split("-")[-1])
        n = max(n, idx)
    return n


def run_rotation():
    n = domain_count()
    if n < 2:
        print("need running federation", file=sys.stderr)
        sys.exit(1)

    tok = kc.admin_token(ROTATE_DOMAIN)
    pre_kid = get_current_kid(ROTATE_DOMAIN, tok)
    print(f"[rotation] old kid = {pre_kid}", file=sys.stderr)

    t0 = time.time()
    kc.rotate_signing_key(ROTATE_DOMAIN, tok)
    t1 = time.time()
    orch.record_epoch("rotation_start", t0)
    orch.record_epoch("rotation_stop", t1)
    print(f"[rotation] metric3 rotate_call = {t1 - t0:.3f}s", file=sys.stderr)

    new_kid = ""
    deadline = time.time() + 30
    while time.time() < deadline:
        new_kid = get_current_kid(ROTATE_DOMAIN, tok)
        if new_kid and new_kid != pre_kid:
            break
        time.sleep(0.1)
    print(f"[rotation] new kid = {new_kid}", file=sys.stderr)
    if not new_kid or new_kid == pre_kid:
        print("ERROR: rotation did not produce a new active kid", file=sys.stderr)
        sys.exit(1)

    alias = f"{orch.FEDERATION_ID}-{kc.realm_name(ROTATE_DOMAIN)}"

    repo_client.notify_key_rotated(kc.realm_name(ROTATE_DOMAIN))
    print("[rotation] notified peers via event channel", file=sys.stderr)

    secrets = orch.load_domain_secrets(ROTATE_DOMAIN)
    src_cid = orch.workload_name(ROTATE_DOMAIN, 0)
    src_secret = secrets[src_cid]

    propagated = {}
    pending = [p for p in range(1, n + 1) if p != ROTATE_DOMAIN]
    deadline = time.time() + 60
    while pending and time.time() < deadline:
        subj = mint_fresh_subject_token(ROTATE_DOMAIN, src_cid, src_secret)
        for p in list(pending):
            status = try_exchange_at_peer(p, alias, subj)
            if status == 200:
                propagated[p] = time.time()
                pending.remove(p)
                print(f"[rotation] domain-{p} accepted new-key token", file=sys.stderr)
        if pending:
            time.sleep(0.2)

    if pending:
        print(f"ERROR: kid never propagated to {pending}", file=sys.stderr)
        sys.exit(1)

    t_prop = max(propagated.values())
    orch.record_epoch("propagation_stop", t_prop)
    print(f"[rotation] metric4 propagation = {t_prop - t1:.3f}s", file=sys.stderr)

    t_mesh_stop = orch.drive_full_mesh(n)
    orch.record_epoch("post_rotation_mesh_stop", t_mesh_stop)
    print(f"[rotation] metric5 post-rotation mesh = {t_mesh_stop - t_prop:.3f}s", file=sys.stderr)


if __name__ == "__main__":
    run_rotation()
