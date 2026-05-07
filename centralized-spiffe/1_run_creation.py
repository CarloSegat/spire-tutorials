#!/usr/bin/env python3
"""Orchestrate initial creation of n-cluster federation."""

import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "common"))
import spire_utils
from print_bundle import print_bundle
from format_bundle import format_bundle
from post_bundle import post_bundle_for_server
from create_federation_dynamic import create_federation_dynamic
from update_registration_entries import update_registration_entries
from set_bundle import set_bundle
from fetch_bundles import fetch_bundles

# Add centralized-spiffe to path for measure functions
sys.path.insert(0, str(Path(__file__).parent))
from measure_creation_end import measure_creation_end, record_creation_start


def setup_n_clusters(n):
    print(f"Setting up {n} clusters...", file=sys.stderr)
    result = subprocess.run(
        ["../common/setup_n_clusters.sh", str(n)],
        cwd=str(Path(__file__).parent)
    )
    if result.returncode != 0:
        sys.exit(1)

    time.sleep(3)


def start_centralized_spiffe_binary():
    print(f"Starting centralized-spiffe binary...", file=sys.stderr)
    return subprocess.Popen(
        [str(spire_utils.artefacts_dir() / "bin" / "centralized-spiffe")],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )


def start_listeners(n):
    print(f"Starting SSE listeners for {n} servers...", file=sys.stderr)
    for i in range(1, n + 1):
        print(f"Starting listener for server {i}", file=sys.stderr)
        subprocess.Popen(
            [
                "python3",
                str(Path(__file__).parent / "listen_and_react.py"),
                "--server-num", str(i),
                "--max-server", str(n),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )


def post_bundles_for_each_server(n):
    print(f"Posting bundles for {n} servers...", file=sys.stderr)
    for i in range(1, n + 1):
        print(f"Posting bundle for server {i}", file=sys.stderr)
        post_bundle_for_server(i)
        time.sleep(0.1)


def fetch_bundles_for_each_server(n):
    print(f"Fetching bundles for {n} servers...", file=sys.stderr)
    for i in range(1, n + 1):
        print(f"Fetching bundles for server {i}", file=sys.stderr)
        fetch_bundles(i)


def create_full_mesh_federations(n):
    print(f"Creating federations...", file=sys.stderr)
    for i in range(1, n + 1):
        for ii in range(1, n + 1):
            if ii == i:
                continue
            print(f"Creating federation dynamic for {i} -> {ii}", file=sys.stderr)
            create_federation_dynamic(i, ii)


def update_all_registration_entries(n):
    print(f"Updating registration entries...", file=sys.stderr)
    for i in range(1, n + 1):
        for ii in range(1, n + 1):
            if ii == i:
                continue
            update_registration_entries(i, ii)


def poll_until_workloads_finish(n):
    print(f"Polling for workload completion...", file=sys.stderr)
    while True:
        try:
            measure_creation_end(n)
            break
        except RuntimeError:
            time.sleep(2)


def run_creation(n):
    """
    Create initial n-cluster federation.

    Args:
        n: number of servers to create
    """
    if n < 1:
        print("Error: n must be >= 1", file=sys.stderr)
        sys.exit(1)

    setup_n_clusters(n)

    # The time it takes to setup the clusters is not taken into account for the
    # purpose of measrung how long it takes to form a federation - i.e. clusters
    # are assumed to already exist
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
    poll_until_workloads_finish(n)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: 1_run_creation.py <n>", file=sys.stderr)
        sys.exit(1)

    n = int(sys.argv[1])
    run_creation(n)
