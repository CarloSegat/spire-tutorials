#!/usr/bin/env python3
"""Orchestrate initial creation of n-domain centralized-OAuth federation.

Measures federation creation time:
  t_start: first POST /metadata/register
  t_stop:  last 200 received during full-mesh drive
"""

import sys
import time

import orchestration as orch


def run_creation(n: int):
    if n < 2:
        print("n must be >= 2", file=sys.stderr)
        sys.exit(1)

    orch.start_metadata_repo()
    orch.wait_metadata_repo()

    # Boot Keycloaks, realms, workloads, listeners (in parallel-ish per domain)
    for i in range(1, n + 1):
        print(f"[setup] domain-{i}", file=sys.stderr)
        orch.setup_domain(i)

    # Settle: ensure every listener is subscribed before we publish.
    time.sleep(2)

    print("[creation] t_start", file=sys.stderr)
    t_start = orch.record_epoch("creation_start")

    for i in range(1, n + 1):
        orch.self_register(i)

    # Block until every domain's Keycloak has IDP aliases for every peer.
    print("[creation] waiting for IDP registration to propagate", file=sys.stderr)
    for i in range(1, n + 1):
        for j in range(1, n + 1):
            if i == j:
                continue
            peer = f"domain-{j}"
            if not orch.wait_peer_registered_at(i, peer, timeout=60):
                print(f"ERROR: domain-{i} never registered peer {peer}", file=sys.stderr)
                sys.exit(1)

    print("[creation] driving full mesh", file=sys.stderr)
    t_stop = orch.drive_full_mesh(n)
    orch.record_epoch("creation_stop", t_stop)
    print(f"[creation] elapsed = {t_stop - t_start:.3f}s", file=sys.stderr)
    print(f"{t_stop - t_start:.3f}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: 1_run_creation.py <n>", file=sys.stderr)
        sys.exit(1)
    run_creation(int(sys.argv[1]))
