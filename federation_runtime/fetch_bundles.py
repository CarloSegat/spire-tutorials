#!/usr/bin/env python3
"""Fetch bundles from the variant's repo and set them on a local SPIRE server."""

import sys
from pathlib import Path

import _bootstrap  # noqa: F401  (sys.path side effect)
import spire_utils
from set_bundle import set_bundle
import repo_client


def log_own_bundle_size(server_num):
    own_bundle = spire_utils.spire_server("bundle", "show", "-format", "spiffe", server_num=server_num)
    print(f"Own bundle size: {len(own_bundle)} chars", file=sys.stderr)


def write_bundle_files_locally(qualified_bundles, cwd):
    for bundle in qualified_bundles:
        td = bundle["TrustDomainName"]
        (cwd / f"{td}.json").write_text(bundle["RawBundle"])
        print(f"Wrote bundle for {td}", file=sys.stderr)


def fetch_bundles(server_num, cwd=None):
    """Fetch every bundle in the federation and import them into this server.

    Pulls all bundles via `repo_client.get_bundles()`, writes each one to
    `<cwd>/<td>.json`, then invokes `set_bundle` to feed them to the
    local spire-server.
    """
    cwd = Path(cwd) if cwd is not None else Path.cwd()

    log_own_bundle_size(server_num)
    qualified_bundles = repo_client.get_bundles()
    print(f"Received {len(qualified_bundles)} qualified bundles", file=sys.stderr)
    write_bundle_files_locally(qualified_bundles, cwd)
    set_bundle(server_num, cwd)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: fetch_bundles.py <server_num> [cwd]", file=sys.stderr)
        sys.exit(1)

    server_num = int(sys.argv[1])
    cwd = sys.argv[2] if len(sys.argv) > 2 else None
    fetch_bundles(server_num, cwd)
