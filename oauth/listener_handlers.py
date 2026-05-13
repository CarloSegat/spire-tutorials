#!/usr/bin/env python3
"""Shared event handlers for OAuth federation listeners.

Used by both centralized (SSE) and ledger (polling) variants.
"""

import json
import logging
import sys
import time
from pathlib import Path


def setup_logging(domain_index: int, variant_dir: Path):
    log_file = variant_dir / "logs" / f"listener-domain-{domain_index}.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=log_file, level=logging.INFO, format="%(message)s")


def log(msg: str):
    ts = time.time()
    logging.info(f"{ts} {msg}")
    print(f"[listener] {msg}", file=sys.stderr)


def write_peers_file(domain_index: int, peers: dict, pids_dir: Path):
    peers_file = pids_dir / f"peers-domain-{domain_index}.json"
    with open(peers_file, "w") as f:
        json.dump(peers, f)
    log(f"wrote peers file: {peers_file}")


def handle_add(domain_index: int, own_domain: str, ev: dict, tok: str, kc):
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


def handle_remove(domain_index: int, own_domain: str, ev: dict, tok: str, kc):
    peer = ev.get("domain_name")
    if peer == own_domain:
        return
    fid = ev.get("federation_id")
    name = f"{fid}-{peer}"
    log(f"peer_remove {peer} {time.time()}")
    kc.disable_idp(domain_index, tok, name)
    kc.set_client_not_before(domain_index, tok, name, int(time.time()))
    log(f"peer_revoked {peer} {time.time()}")
