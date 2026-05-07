#!/usr/bin/env python3
"""Fetch bundles from centralized repository and set them locally."""

import json
import sys
from pathlib import Path
import requests

sys.path.insert(0, str(Path(__file__).parent.parent / "common"))
import spire_utils
from set_bundle import set_bundle

def log_own_bundle_size(server_num):
    own_bundle = spire_utils.spire_server("bundle", "show", "-format", "spiffe", server_num=server_num)
    print(f"Own bundle size: {len(own_bundle)} chars", file=sys.stderr)


def fetch_qualified_bundles_from_repo():
    print(f"Fetching bundles from http://localhost:8080/bundles/test", file=sys.stderr)
    response = requests.get("http://localhost:8080/bundles/test")
    response.raise_for_status()

    qualified_bundles = response.json().get("QualifiedBundles", [])
    print(f"Received {len(qualified_bundles)} qualified bundles", file=sys.stderr)
    return qualified_bundles


def write_bundle_files_locally(qualified_bundles, cwd):
    for bundle in qualified_bundles:
        td = bundle["TrustDomainName"]
        raw_bundle = bundle["RawBundle"]

        bundle_file = cwd / f"{td}.json"
        bundle_file.write_text(raw_bundle)
        print(f"Wrote bundle for {td}", file=sys.stderr)


def fetch_bundles(server_num, cwd=None):
    """
    Fetch all bundles from centralized repository and set them on this server.

    Args:
        server_num: server number
        cwd: working directory to write bundle files (default: current)
    """
    cwd = Path(cwd) if cwd is not None else Path.cwd()

    log_own_bundle_size(server_num)
    qualified_bundles = fetch_qualified_bundles_from_repo()
    write_bundle_files_locally(qualified_bundles, cwd)
    set_bundle(server_num, cwd)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: fetch_bundles.py <server_num> [cwd]", file=sys.stderr)
        sys.exit(1)

    server_num = int(sys.argv[1])
    cwd = sys.argv[2] if len(sys.argv) > 2 else None
    fetch_bundles(server_num, cwd)
