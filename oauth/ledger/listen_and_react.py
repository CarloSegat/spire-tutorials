#!/usr/bin/env python3
"""Per-domain listener: polls OAuthMetadataStore contract events (ledger variant).

For each peer K added to federation F, calls the LOCAL Keycloak admin
API to create IDP alias `F-K` (pointing at K's JWKS) plus a public
exchange client `F-K`. On remove, disables the IDP and bumps the
matching client's `notBefore` for hard-stop revocation.
"""

import argparse
import sys
from pathlib import Path

VARIANT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(VARIANT_DIR.parent))

import keycloak as kc
import repo_client
from listener_handlers import setup_logging, log, write_peers_file, handle_add, handle_remove

PIDS_DIR = VARIANT_DIR / "pids"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain-index", type=int, required=True)
    args = ap.parse_args()

    domain_index = args.domain_index
    own_domain = kc.realm_name(domain_index)
    setup_logging(domain_index, VARIANT_DIR)
    log(f"listener started for {own_domain}")

    tok = kc.admin_token(domain_index)
    kc.bump_master_token_lifespan(domain_index, tok, 86400)

    # Create event filters FIRST so events emitted during backfill are captured
    filters = repo_client.create_event_filters()

    seen = set()
    peers = {}
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
        handle_add(domain_index, own_domain, ev, tok, kc)
        peers[peer] = m.get("KeycloakURL")
        seen.add(peer)
    write_peers_file(domain_index, peers, PIDS_DIR)

    try:
        for ev in repo_client.poll_events(filters):
            t = ev.get("type")
            peer = ev.get("domain_name")
            try:
                if t == "domain_added":
                    if peer in seen:
                        continue
                    handle_add(domain_index, own_domain, ev, tok, kc)
                    peers[peer] = ev.get("keycloak_url")
                    seen.add(peer)
                    write_peers_file(domain_index, peers, PIDS_DIR)
                elif t == "domain_removed":
                    handle_remove(domain_index, own_domain, ev, tok, kc)
                    peers.pop(peer, None)
                    seen.discard(peer)
                    write_peers_file(domain_index, peers, PIDS_DIR)
            except Exception as e:
                log(f"ERROR handling {t} {peer}: {e}")
    except KeyboardInterrupt:
        log("listener shutting down")
    except Exception as e:
        log(f"ERROR: listener failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
