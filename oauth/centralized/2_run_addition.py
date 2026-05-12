#!/usr/bin/env python3
"""Add 1 domain to an existing centralized-OAuth federation.

Picks next free domain index based on existing pid files. Measures:
  t_start: POST /metadata/register for the new domain
  t_stop:  last 200 in bidirectional full-mesh between new domain and all existing
"""

import concurrent.futures
import sys
import time

import requests

import orchestration as orch


def existing_domain_count() -> int:
    """Highest domain-N for which a listener pid file exists."""
    n = 0
    for f in orch.PID_DIR.glob("listener-domain-*.pid"):
        idx = int(f.stem.split("-")[-1])
        n = max(n, idx)
    return n


def drive_bidirectional_mesh(new_dom: int, existing: int, retry_sleep=0.1):
    """All ordered (src,tgt) pairs where exactly one of src/tgt is new_dom."""
    pairs = []
    for other in range(1, existing + 1):
        if other == new_dom:
            continue
        for si in range(orch.WORKLOADS_PER_DOMAIN):
            for ti in range(orch.WORKLOADS_PER_DOMAIN):
                pairs.append((new_dom, si, other, ti))
                pairs.append((other, si, new_dom, ti))

    def attempt(p):
        sd, si, td, ti = p
        while True:
            try:
                s, _ = orch.call_pair(sd, si, td, ti)
                if s == 200:
                    return p, time.time()
            except requests.RequestException:
                pass
            time.sleep(retry_sleep)

    last = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as ex:
        for fut in concurrent.futures.as_completed([ex.submit(attempt, p) for p in pairs]):
            pair, ts = fut.result()
            last[pair] = ts
    return max(last.values())


def run_addition():
    existing = existing_domain_count()
    if existing < 2:
        print("need >=2 existing domains", file=sys.stderr)
        sys.exit(1)
    new_dom = existing + 1
    print(f"[addition] adding domain-{new_dom} to federation of {existing}", file=sys.stderr)

    orch.setup_domain(new_dom)
    time.sleep(2)  # listener subscribe settle

    t_start = orch.record_epoch("addition_start")
    orch.self_register(new_dom)

    # Wait for IDP-cross-registration to settle
    new_realm = f"domain-{new_dom}"
    for i in range(1, existing + 1):
        if not orch.wait_peer_registered_at(i, new_realm, timeout=60):
            print(f"ERROR: domain-{i} never registered new peer {new_realm}", file=sys.stderr)
            sys.exit(1)
    for j in range(1, existing + 1):
        peer = f"domain-{j}"
        if not orch.wait_peer_registered_at(new_dom, peer, timeout=60):
            print(f"ERROR: domain-{new_dom} never registered peer {peer}", file=sys.stderr)
            sys.exit(1)

    t_stop = drive_bidirectional_mesh(new_dom, existing)
    orch.record_epoch("addition_stop", t_stop)
    print(f"[addition] elapsed = {t_stop - t_start:.3f}s", file=sys.stderr)
    print(f"{t_stop - t_start:.3f}")


if __name__ == "__main__":
    run_addition()
