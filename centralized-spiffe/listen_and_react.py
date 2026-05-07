#!/usr/bin/env python3

import argparse
import json
import logging
import sys
import tempfile
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

from common.spire_utils import spire_server, trust_domain, server_dir
from common.format_bundle import format_bundle


def setup_logging(server_num):
    log_file = server_dir(server_num) / "listener.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=log_file,
        level=logging.INFO,
        format='%(message)s'
    )


def log_event(msg):
    ts = time.time()
    logging.info(f"{ts} {msg}")
    print(f"[listener] {msg}")


def fetch_and_apply_bundle(trust_domain_name, server_num, max_server):
    try:
        resp = requests.get("http://localhost:8080/bundles/test", timeout=5)
        resp.raise_for_status()
        bundles_resp = resp.json()

        # Find the bundle for the rotated trust domain
        bundle_data = None
        for qb in bundles_resp.get("QualifiedBundles", []):
            if qb["TrustDomainName"] == trust_domain_name:
                bundle_data = qb
                break

        if not bundle_data:
            log_event(f"ERROR: bundle for {trust_domain_name} not found in repo")
            return False

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tf:
            tf.write(bundle_data["RawBundle"])
            tmp_file = tf.name

        try:
            spire_server("bundle", "set", "-id", trust_domain_name, "-path", tmp_file, "-format", "spiffe", server_num=server_num)
            ts = time.time()
            log_event(f"bundle_applied {trust_domain_name} {ts}")
            return True
        except Exception as e:
            log_event(f"ERROR: failed to apply bundle: {e}")
            return False
        finally:
            Path(tmp_file).unlink(missing_ok=True)
    except Exception as e:
        log_event(f"ERROR: failed to fetch bundle: {e}")
        return False


def listen_for_events(server_num, max_server):
    own_td = trust_domain(server_num)

    try:
        resp = requests.get("http://localhost:8080/events", stream=True, timeout=None)
        resp.raise_for_status()
        log_event(f"connected to SSE stream")

        for line in resp.iter_lines():
            if not line:
                continue

            line = line.decode('utf-8') if isinstance(line, bytes) else line

            if not line.startswith('data: '):
                continue

            try:
                event_data = json.loads(line[6:])  # Skip 'data: ' prefix
                event_type = event_data.get("type")
                event_trust_domain = event_data.get("data", {}).get("trust_domain")

                if event_type == "bundle_updated":
                    ts = time.time()
                    log_event(f"bundle_received {event_trust_domain} {ts}")

                    # Skip own bundle
                    if event_trust_domain != own_td:
                        fetch_and_apply_bundle(event_trust_domain, server_num, max_server)

                elif event_type == "bundle_deleted":
                    ts = time.time()
                    log_event(f"bundle_received_delete {event_trust_domain} {ts}")

                    if event_trust_domain != own_td:
                        try:
                            spire_server("bundle", "delete", "-id", event_trust_domain, server_num=server_num)
                            log_event(f"bundle_deleted {event_trust_domain} {time.time()}")
                        except Exception as e:
                            log_event(f"ERROR: failed to delete bundle: {e}")

            except json.JSONDecodeError as e:
                log_event(f"ERROR: failed to parse event: {e}")
                continue

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
    listen_for_events(args.server_num, args.max_server)


if __name__ == "__main__":
    main()
