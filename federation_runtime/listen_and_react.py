#!/usr/bin/env python3
"""Per-server event listener: reacts to bundle update/delete events."""

import argparse
import logging
import sys
import time

import _bootstrap  # noqa: F401  (sys.path side effect)
import spire_utils
import repo_client
from orchestration import apply_raw_bundle


def setup_logging(server_num):
    log_file = spire_utils.server_dir(server_num) / "listener.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=log_file, level=logging.INFO, format='%(message)s')


def log_event(msg):
    ts = time.time()
    logging.info(f"{ts} {msg}")
    print(f"[listener] {msg}")


def fetch_and_apply_bundle(td, server_num):
    """Pull the latest bundle for `td` from the repo and import it locally."""
    try:
        bundle = next(
            (qb for qb in repo_client.get_bundles() if qb["TrustDomainName"] == td),
            None,
        )
        if bundle is None:
            log_event(f"ERROR: bundle for {td} not found in repo")
            return False

        apply_raw_bundle(td, bundle["RawBundle"], server_num)
        log_event(f"bundle_applied {td} {time.time()}")
        return True
    except Exception as e:
        log_event(f"ERROR: failed to apply bundle for {td}: {e}")
        return False


def handle_event(event, own_td, server_num):
    event_type = event.get("type")
    event_td = event.get("data", {}).get("trust_domain")

    if event_type == "bundle_updated":
        log_event(f"bundle_received {event_td} {time.time()}")
        if event_td != own_td:
            fetch_and_apply_bundle(event_td, server_num)

    elif event_type == "bundle_deleted":
        log_event(f"bundle_received_delete {event_td} {time.time()}")
        if event_td != own_td:
            try:
                spire_utils.spire_server(
                    "bundle", "delete",
                    "-id", event_td, "-mode", "dissociate",
                    server_num=server_num,
                )
                log_event(f"bundle_deleted {event_td} {time.time()}")
            except Exception as e:
                log_event(f"ERROR: failed to delete bundle for {event_td}: {e}")


def listen_for_events(server_num):
    own_td = spire_utils.trust_domain(server_num)
    try:
        log_event("connected to event stream")
        for event in repo_client.stream_events():
            handle_event(event, own_td, server_num)
    except KeyboardInterrupt:
        log_event("listener shutting down")
    except Exception as e:
        log_event(f"ERROR: listener failed: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--server-num", type=int, required=True)
    parser.add_argument("--max-server", type=int, required=True)
    args = parser.parse_args()

    setup_logging(args.server_num)
    log_event(f"listener started for server {args.server_num}")
    listen_for_events(args.server_num)


if __name__ == "__main__":
    main()
