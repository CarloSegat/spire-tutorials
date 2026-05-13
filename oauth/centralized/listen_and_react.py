#!/usr/bin/env python3
"""Per-domain listener: subscribes to OAuth metadata events.

For each peer K added to federation F, calls the LOCAL Keycloak admin
API to create IDP alias `F-K` (pointing at K's JWKS) plus a public
exchange client `F-K`. On remove, disables the IDP and bumps the
matching client's `notBefore` for hard-stop revocation.
"""

import argparse
import logging
import sys
import time
from pathlib import Path

import keycloak as kc
import repo_client
import json


PIDS_DIR = Path(__file__).resolve().parent / "pids"


def write_peers_file(domain_index: int, peers: dict):
    """Write peers-domain-N.json with domain_name -> keycloak_url mapping."""
    peers_file = PIDS_DIR / f"peers-domain-{domain_index}.json"
    with open(peers_file, "w") as f:
        json.dump(peers, f)
    log(f"wrote peers file: {peers_file}")


def setup_logging(domain_index: int):
    log_file = Path(__file__).resolve().parent / "logs" / f"listener-domain-{domain_index}.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=log_file, level=logging.INFO, format="%(message)s")


def log(msg: str):
    ts = time.time()
    logging.info(f"{ts} {msg}")
    print(f"[listener] {msg}", file=sys.stderr)


def handle_add(domain_index: int, own_domain: str, ev: dict, tok: str):
    peer = ev.get("domain_name")
    if peer == own_domain:
        return
    fid = ev.get("federation_id")
    peer_jwks = ev.get("jwks_url")
    peer_kc = ev.get("keycloak_url")
    issuer = f"{peer_kc}/realms/{peer}"
    name = f"{fid}-{peer}"
    log(f"peer_add {peer} {time.time()}")
    kc.create_idp_alias(domain_index, tok, name, peer_jwks, issuer)
    kc.create_public_exchange_client(domain_index, tok, name)
    kc.allow_client_to_exchange(domain_index, tok, name, name)
    log(f"peer_registered {peer} {time.time()}")


def handle_remove(domain_index: int, own_domain: str, ev: dict, tok: str):
    peer = ev.get("domain_name")
    if peer == own_domain:
        return
    fid = ev.get("federation_id")
    name = f"{fid}-{peer}"
    log(f"peer_remove {peer} {time.time()}")
    kc.disable_idp(domain_index, tok, name)
    kc.set_client_not_before(domain_index, tok, name, int(time.time()))
    log(f"peer_revoked {peer} {time.time()}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain-index", type=int, required=True)
    args = ap.parse_args()

    domain_index = args.domain_index
    own_domain = kc.realm_name(domain_index)
    setup_logging(domain_index)
    log(f"listener started for {own_domain}")

    tok = kc.admin_token(domain_index)
    kc.bump_master_token_lifespan(domain_index, tok, 86400)

    # Open SSE first so any event after this point is queued, then backfill
    # existing peers from a snapshot. Dedup via `seen` so events that overlap
    # with the snapshot are not double-handled.
    stream = repo_client.open_event_stream()
    seen = set()
    peers = {}  # domain_name -> keycloak_url
    for m in repo_client.list_metadata():
        peer = m.get("DomainName")
        if peer == own_domain or peer in seen:
            continue
        ev = {
            "type": "domain_added",
            "federation_id": repo_client.FEDERATION_ID,
            "domain_name": peer,
            "keycloak_url": m.get("KeycloakURL"),
            "jwks_url": m.get("JWKSURL"),
        }
        handle_add(domain_index, own_domain, ev, tok)
        peers[peer] = m.get("KeycloakURL")
        seen.add(peer)
    write_peers_file(domain_index, peers)

    try:
        for ev in repo_client.iter_events(stream):
            t = ev.get("type")
            peer = ev.get("domain_name")
            try:
                if t == "domain_added":
                    if peer in seen:
                        continue
                    handle_add(domain_index, own_domain, ev, tok)
                    peers[peer] = ev.get("keycloak_url")
                    seen.add(peer)
                    write_peers_file(domain_index, peers)
                elif t == "domain_removed":
                    handle_remove(domain_index, own_domain, ev, tok)
                    peers.pop(peer, None)
                    seen.discard(peer)
                    write_peers_file(domain_index, peers)
            except Exception as e:
                log(f"ERROR handling {t} {peer}: {e}")
    except KeyboardInterrupt:
        log("listener shutting down")
    except Exception as e:
        log(f"ERROR: listener failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
