#!/usr/bin/env python3
"""Orchestrate adding a single server to an existing federation."""

import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "common"))
import spire_utils
from post_bundle import post_bundle_for_server
from create_federation_dynamic import create_federation_dynamic
from update_registration_entries import update_registration_entries
from fetch_bundles import fetch_bundles

sys.path.insert(0, str(Path(__file__).parent))
from measure_addition_end import measure_addition_end, record_addition_start

def detect_next_server_number():
    server_dir = spire_utils.artefacts_dir() / "server"

    if not server_dir.exists():
        print("Error: artefacts/server/ not found", file=sys.stderr)
        sys.exit(1)

    max_server = 0
    for d in server_dir.iterdir():
        if d.is_dir():
            try:
                num = int(d.name)
                if num > max_server:
                    max_server = num
            except ValueError:
                pass

    return max_server + 1


def setup_new_cluster(n):
    print(f"Setting up cluster {n}...", file=sys.stderr)
    result = subprocess.run(
        ["./set_up_cluster.sh", str(n), str(n)],
        cwd=str(Path(__file__).parent.parent / "set_up")
    )
    if result.returncode != 0:
        sys.exit(1)

    time.sleep(3)


def post_bundle_for_new_server(n):
    print(f"Posting bundle for server {n}...", file=sys.stderr)
    post_bundle_for_server(n)


def fetch_bundles_for_new_server(n):
    print(f"Fetching bundles for server {n}...", file=sys.stderr)
    fetch_bundles(n)


def create_federations_from_new_server(n):
    print(f"Creating federations from new server {n}...", file=sys.stderr)
    for ii in range(1, n):
        print(f"Creating federation dynamic for {n} -> {ii}", file=sys.stderr)
        create_federation_dynamic(n, ii)


def update_registration_entries_for_new_server(n):
    print(f"Updating registration entries for new server {n}...", file=sys.stderr)
    for ii in range(1, n):
        update_registration_entries(n, ii)


def start_listener_for_new_server(n):
    print(f"Starting SSE listener for server {n}...", file=sys.stderr)
    # Determine max_server based on existing servers
    server_dir = spire_utils.artefacts_dir() / "server"
    max_server = 0
    for d in server_dir.iterdir():
        if d.is_dir():
            try:
                num = int(d.name)
                if num > max_server:
                    max_server = num
            except ValueError:
                pass

    subprocess.Popen(
        [
            "python3",
            str(Path(__file__).parent / "listen_and_react.py"),
            "--server-num", str(n),
            "--max-server", str(max_server),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    time.sleep(0.5)


def poll_until_workloads_finish(n):
    print(f"Polling for workload completion...", file=sys.stderr)
    while True:
        try:
            measure_addition_end(n)
            break
        except RuntimeError:
            time.sleep(2)


def run_addition():
    """
    Add a single new server to an existing federation.

    Auto-detects the next server number from artefacts/server/.
    """
    n = detect_next_server_number()
    print(f"Adding server {n} to the federation", file=sys.stderr)

    setup_new_cluster(n)
    start_listener_for_new_server(n)
    record_addition_start(n)

    post_bundle_for_new_server(n)
    fetch_bundles_for_new_server(n)
    time.sleep(0.1)

    create_federations_from_new_server(n)
    time.sleep(1)

    update_registration_entries_for_new_server(n)
    poll_until_workloads_finish(n)

if __name__ == "__main__":
    run_addition()
