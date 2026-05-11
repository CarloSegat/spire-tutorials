#!/usr/bin/env python3
"""Orchestrate adding a single server to an existing federation."""

import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "common"))
from create_federation_dynamic import create_federation_dynamic
from update_registration_entries import update_registration_entries
from fetch_bundles import fetch_bundles

sys.path.insert(0, str(Path(__file__).parent))
import repo_client
from orchestration import start_listener, get_max_server_number, poll_until
from measure_addition_end import measure_addition_end, record_addition_start


def setup_new_cluster(n):
    print(f"Setting up cluster {n}...", file=sys.stderr)
    result = subprocess.run(
        ["./set_up_cluster.sh", str(n), str(n)],
        cwd=str(Path(__file__).parent.parent / "set_up"),
    )
    if result.returncode != 0:
        sys.exit(1)
    time.sleep(3)


def create_federations_from_new_server(n):
    print(f"Creating federations from new server {n}...", file=sys.stderr)
    for ii in range(1, n):
        print(f"Creating federation dynamic for {n} -> {ii}", file=sys.stderr)
        create_federation_dynamic(n, ii)


def update_registration_entries_for_new_server(n):
    print(f"Updating registration entries for new server {n}...", file=sys.stderr)
    for ii in range(1, n):
        update_registration_entries(n, ii)


def run_addition():
    """Add a single new server to an existing federation.

    Auto-detects the next server number from artefacts/server/.
    """
    n = get_max_server_number() + 1
    if n < 2:
        print("Error: artefacts/server/ has no existing servers to add to", file=sys.stderr)
        sys.exit(1)
    print(f"Adding server {n} to the federation", file=sys.stderr)

    setup_new_cluster(n)

    max_server = get_max_server_number()
    print(f"Starting SSE listener for server {n}...", file=sys.stderr)
    start_listener(n, max_server)
    time.sleep(0.5)

    record_addition_start(n)
    repo_client.publish_bundle_for_server(n, "put")

    print(f"Fetching bundles for server {n}...", file=sys.stderr)
    fetch_bundles(n)
    time.sleep(0.1)

    create_federations_from_new_server(n)
    time.sleep(1)

    update_registration_entries_for_new_server(n)

    print("Polling for workload completion...", file=sys.stderr)
    poll_until(measure_addition_end, n, sleep=2)


if __name__ == "__main__":
    run_addition()
