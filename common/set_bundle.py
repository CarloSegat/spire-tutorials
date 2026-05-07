#!/usr/bin/env python3
"""Ingest peer bundle JSON files into a server."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import spire_utils

def find_bundle_files(cwd):
    return list(cwd.glob("*.snet.example.json"))


def server_num_from_bundle_filename(bundle_file):
    num_str = bundle_file.name.split(".")[0]
    try:
        return int(num_str)
    except ValueError:
        return None


def set_one_bundle(server_num, bundle_file, peer_num):
    td = spire_utils.trust_domain(peer_num)
    print(f"Setting bundle for {td} on server {server_num}", file=sys.stderr)

    spire_utils.spire_server(
        "bundle", "set",
        "-id", td,
        "-path", str(bundle_file),
        "-format", "spiffe",
        server_num=server_num
    )


def delete_bundle_files(bundle_files):
    for bundle_file in bundle_files:
        bundle_file.unlink()


def set_bundle(server_num, cwd=None):
    """
    Set bundles from JSON files in the current directory.

    Scans for *.snet.example.json files, skips own server's bundle,
    calls spire-server bundle set for each, then deletes the files.

    Args:
        server_num: server number (used to skip own bundle)
        cwd: working directory to scan (default: current)
    """
    cwd = Path(cwd) if cwd is not None else Path.cwd()

    bundle_files = find_bundle_files(cwd)

    for bundle_file in bundle_files:
        peer_num = server_num_from_bundle_filename(bundle_file)
        if peer_num is None:
            continue

        if peer_num == server_num:
            print(f"Skipping own bundle: {bundle_file.name}", file=sys.stderr)
            continue

        set_one_bundle(server_num, bundle_file, peer_num)

    delete_bundle_files(bundle_files)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: set_bundle.py <server_num> [cwd]", file=sys.stderr)
        sys.exit(1)

    server_num = int(sys.argv[1])
    cwd = sys.argv[2] if len(sys.argv) > 2 else None
    set_bundle(server_num, cwd)
