#!/usr/bin/env python3
"""Orchestrate initial creation of n-cluster federation (ledger variant).

The ledger variant brings up a fresh Hardhat node, compiles & deploys the
SpiffeBundleStore contract, and clears any stale artefacts before
delegating to the variant-agnostic creation flow.
"""

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

VARIANT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = VARIANT_DIR.parent.parent
os.environ.setdefault("FEDERATION_VARIANT_DIR", str(VARIANT_DIR))
sys.path.insert(0, str(VARIANT_DIR))
sys.path.insert(0, str(PROJECT_ROOT / "federation_runtime"))
sys.path.insert(0, str(PROJECT_ROOT / "common"))

import spire_utils
from create_federation_dynamic import create_federation_dynamic
from update_registration_entries import update_registration_entries

import repo_client
from fetch_bundles import fetch_bundles
from orchestration import start_listener, poll_until
from measure_creation_end import measure_creation_end, record_creation_start

HARDHAT_DIR = VARIANT_DIR / "hardhat"
HARDHAT_PORT = 8545
CONTRACT_ADDRESS_FILE = VARIANT_DIR / "contract_address.txt"
NPX = shutil.which("npx") or "npx"


def kill_existing_hardhat():
    """Best-effort: kill any hardhat node listening on :8545."""
    subprocess.run(
        ["pkill", "-f", "hardhat node"],
        stderr=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
    )
    time.sleep(0.5)


def start_hardhat_node():
    """Spawn `npx hardhat node` and wait until the RPC endpoint answers."""
    print("Starting Hardhat node on :8545...", file=sys.stderr)
    log_file = VARIANT_DIR / "hardhat.log"
    proc = subprocess.Popen(
        f"{NPX} hardhat node 2>&1 | tee {log_file}",
        cwd=str(HARDHAT_DIR),
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    import socket
    for _ in range(40):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.25)
            try:
                if s.connect_ex(("127.0.0.1", HARDHAT_PORT)) == 0:
                    return proc
            except OSError:
                pass
        time.sleep(0.25)
    raise RuntimeError(f"Hardhat node did not open :{HARDHAT_PORT} within 10s")


def compile_contract():
    print("Compiling SpiffeBundleStore...", file=sys.stderr)
    result = subprocess.run(
        [NPX, "hardhat", "compile"],
        cwd=str(HARDHAT_DIR),
    )
    if result.returncode != 0:
        sys.exit(1)


def deploy_contract():
    """Run scripts/deploy.js against the localhost network and poll for the address file."""
    print("Deploying SpiffeBundleStore...", file=sys.stderr)
    CONTRACT_ADDRESS_FILE.unlink(missing_ok=True)
    result = subprocess.run(
        [NPX, "hardhat", "run", "scripts/deploy.js", "--network", "localhost"],
        cwd=str(HARDHAT_DIR),
    )
    if result.returncode != 0:
        sys.exit(1)

    for _ in range(40):
        if CONTRACT_ADDRESS_FILE.exists():
            print(f"Deployed at {CONTRACT_ADDRESS_FILE.read_text().strip()}", file=sys.stderr)
            return
        time.sleep(0.25)
    raise RuntimeError(f"contract_address.txt not produced within 10s at {CONTRACT_ADDRESS_FILE}")


def clear_old_artefacts():
    """Wipe artefacts/ so old logs don't contaminate this run's measurements."""
    artefacts = spire_utils.artefacts_dir()
    if not artefacts.exists():
        return
    for child in artefacts.iterdir():
        if child.name == "bin":
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
    print(f"Cleared {artefacts} (preserved bin/)", file=sys.stderr)


def setup_n_clusters(n):
    print(f"Setting up {n} clusters...", file=sys.stderr)
    result = subprocess.run(
        ["./setup_n_clusters.sh", str(n)],
        cwd=str(PROJECT_ROOT / "common"),
    )
    if result.returncode != 0:
        sys.exit(1)
    time.sleep(3)


def start_listeners(n):
    print(f"Starting event listeners for {n} servers...", file=sys.stderr)
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
    """Create initial n-cluster federation on top of a fresh Hardhat node + contract."""
    if n < 1:
        print("Error: n must be >= 1", file=sys.stderr)
        sys.exit(1)

    kill_existing_hardhat()
    clear_old_artefacts()
    start_hardhat_node()
    compile_contract()
    deploy_contract()

    setup_n_clusters(n)

    # Cluster setup time is excluded from federation-creation timing on purpose:
    # clusters are assumed to already exist when a federation forms.
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
