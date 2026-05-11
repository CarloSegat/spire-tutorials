#!/usr/bin/env python3
"""Orchestrate initial creation of n-cluster federation."""

import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "common"))
import spire_utils
from create_federation_dynamic import create_federation_dynamic
from update_registration_entries import update_registration_entries
from fetch_bundles import fetch_bundles

sys.path.insert(0, str(Path(__file__).parent))
import repo_client
from orchestration import start_listener, poll_until
from measure_creation_end import measure_creation_end, record_creation_start


def setup_n_clusters(n):
    print(f"Setting up {n} clusters...", file=sys.stderr)
    result = subprocess.run(
        ["../common/setup_n_clusters.sh", str(n)],
        cwd=str(Path(__file__).parent),
    )
    if result.returncode != 0:
        sys.exit(1)
    time.sleep(3)


def start_centralized_spiffe_binary():
    print("Starting centralized-spiffe binary...", file=sys.stderr)
    return subprocess.Popen(
        [str(spire_utils.artefacts_dir() / "bin" / "centralized-spiffe")],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def start_listeners(n):
    print(f"Starting SSE listeners for {n} servers...", file=sys.stderr)
    for i in range(1, n + 1):
        print(f"Starting listener for server {i}", file=sys.stderr)
        start_listener(i, n)


def post_bundles_for_each_server(n):
    print(f"Posting bundles for {n} servers...", file=sys.stderr)
    for i in range(1, n + 1):
        repo_client.publish_bundle_for_server(i, "post")
        time.sleep(0.1)


def fetch_bundles_for_each_server(n):
    print(f"Fetching bundles for {n} servers...", file=sys.stderr)
    for i in range(1, n + 1):
        fetch_bundles(i)


def create_full_mesh_federations(n):
    print("Creating federations...", file=sys.stderr)
    for i in range(1, n + 1):
        for ii in range(1, n + 1):
            if ii == i:
                continue
            print(f"Creating federation dynamic for {i} -> {ii}", file=sys.stderr)
            create_federation_dynamic(i, ii)


def update_all_registration_entries(n):
    print("Updating registration entries...", file=sys.stderr)
    for i in range(1, n + 1):
        for ii in range(1, n + 1):
            if ii == i:
                continue
            update_registration_entries(i, ii)


def run_creation(n):
    """Create initial n-cluster federation."""
    if n < 1:
        print("Error: n must be >= 1", file=sys.stderr)
        sys.exit(1)

    setup_n_clusters(n)

    # Cluster setup time is excluded from federation-creation timing on purpose:
    # clusters are assumed to already exist when a federation forms.
    start_centralized_spiffe_binary()
    time.sleep(1)
    start_listeners(n)
    time.sleep(1)
    record_creation_start()

    post_bundles_for_each_server(n)
    time.sleep(0.1)

    fetch_bundles_for_each_server(n)
    time.sleep(0.1)

    create_full_mesh_federations(n)
    time.sleep(1)

    update_all_registration_entries(n)

    print("Polling for workload completion...", file=sys.stderr)
    poll_until(measure_creation_end, n, sleep=2)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: 1_run_creation.py <n>", file=sys.stderr)
        sys.exit(1)
    run_creation(int(sys.argv[1]))
