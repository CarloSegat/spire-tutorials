#!/usr/bin/env python3
"""Web3 client for the SpiffeBundleStore contract.

Exposes the same surface as `centralized-spiffe/repo_client.py` so every
other script in this directory is an unchanged copy of its counterpart.
The HTTP repo's POST/PUT/DELETE/GET/SSE map onto contract transactions
and `eth_getLogs` polling against a local Hardhat node on
http://localhost:8545.
"""

import json
import sys
import time
from pathlib import Path

from web3 import Web3

sys.path.insert(0, str(Path(__file__).parent.parent / "common"))
import spire_utils
from print_bundle import print_bundle
from format_bundle import format_bundle

RPC_URL = "http://localhost:8545"
ABI_PATH = Path(__file__).parent / "hardhat" / "artifacts" / "contracts" / "SpiffeBundleStore.sol" / "SpiffeBundleStore.json"
ADDR_FILE = Path(__file__).parent / "contract_address.txt"
FEDERATION_ID = "test"  # kept only for API parity with the HTTP client

_w3 = None
_contract_cache = None


def _w3_client():
    global _w3
    if _w3 is None:
        _w3 = Web3(Web3.HTTPProvider(RPC_URL))
    return _w3


def _contract():
    """Return a singleton Contract bound to the deployed address.

    Both the ABI (from Hardhat compile artefacts) and the deployment
    address (written by `scripts/deploy.js`) must be present on disk.
    """
    global _contract_cache
    if _contract_cache is not None:
        return _contract_cache

    if not ABI_PATH.exists():
        raise RuntimeError(
            f"ABI not found at {ABI_PATH}. Run `npx hardhat compile` first."
        )
    if not ADDR_FILE.exists():
        raise RuntimeError(
            f"contract_address.txt not found at {ADDR_FILE}. Run the deploy script first."
        )

    abi = json.loads(ABI_PATH.read_text())["abi"]
    addr = _w3_client().to_checksum_address(ADDR_FILE.read_text().strip())
    _contract_cache = _w3_client().eth.contract(address=addr, abi=abi)
    return _contract_cache


def _sender():
    return _w3_client().eth.accounts[0]


def _send(fn):
    """Submit a contract function transaction and wait for the receipt."""
    tx_hash = fn.transact({"from": _sender()})
    return _w3_client().eth.wait_for_transaction_receipt(tx_hash)


def _extract(formatted):
    """Parse a format_bundle JSON envelope and pull out (td, raw)."""
    obj = json.loads(formatted) if isinstance(formatted, str) else formatted
    qb = obj["QualifiedBundle"]
    return qb["TrustDomainName"], qb["RawBundle"]


def post_bundle(formatted):
    """Submit a never-seen trust domain's bundle to the contract.

    Args:
        formatted: JSON string/dict produced by `common.format_bundle.format_bundle`.

    Returns:
        (status_code, response_text) tuple. Status is 200 on success or
        500 on any transaction error, mirroring the HTTP client's shape.
    """
    td, raw = _extract(formatted)
    try:
        _send(_contract().functions.postBundle(td, raw))
        return 200, "ok"
    except Exception as e:
        return 500, str(e)


def upsert_bundle(formatted):
    """Update an existing bundle, falling back to post if it doesn't exist yet.

    Mirrors HTTP PUT semantics (insert-or-update). Used during addition
    and rotation.
    """
    td, raw = _extract(formatted)
    c = _contract()
    try:
        if c.functions.exists(td).call():
            _send(c.functions.updateBundle(td, raw))
        else:
            _send(c.functions.postBundle(td, raw))
        return 200, "ok"
    except Exception as e:
        return 500, str(e)


def delete_bundle(server_num):
    """Remove this server's trust domain bundle from the contract.

    Triggers a BundleDeleted event that listeners react to during member
    removal.
    """
    td = spire_utils.trust_domain(server_num)
    try:
        _send(_contract().functions.deleteBundle(td))
        print(f"Delete response: 200 ok", file=sys.stderr)
        return 200, "ok"
    except Exception as e:
        print(f"Delete response: 500 {e}", file=sys.stderr)
        return 500, str(e)


def get_bundles():
    """Read every bundle currently held by the contract.

    Walks the contract's paginated read API and returns a flat list of
    QualifiedBundle dicts in the same shape the HTTP repo returned.
    """
    c = _contract()
    limit = 50
    offset = 0
    out = []
    while True:
        tds, raws, total = c.functions.getAllBundles(offset, limit).call()
        for td, raw in zip(tds, raws):
            out.append({"TrustDomainName": td, "RawBundle": raw})
        if len(out) >= total or not tds:
            break
        offset += limit
    return out


def stream_events(poll_interval=0.5):
    """Subscribe to the contract's bundle events as a generator.

    Uses block-range scanning instead of filters to avoid Hardhat
    silently expiring filters and dropping events.
    """
    c = _contract()
    w3 = _w3_client()
    last_block = w3.eth.block_number

    while True:
        current = w3.eth.block_number
        if current > last_block:
            for ev in c.events.BundlePosted.get_logs(from_block=last_block + 1, to_block=current):
                yield {"type": "bundle_updated", "data": {"trust_domain": ev["args"]["trustDomain"]}}
            for ev in c.events.BundleUpdated.get_logs(from_block=last_block + 1, to_block=current):
                yield {"type": "bundle_updated", "data": {"trust_domain": ev["args"]["trustDomain"]}}
            for ev in c.events.BundleDeleted.get_logs(from_block=last_block + 1, to_block=current):
                yield {"type": "bundle_deleted", "data": {"trust_domain": ev["args"]["trustDomain"]}}
            last_block = current
        time.sleep(poll_interval)


def publish_bundle_for_server(server_num, verb):
    """Read this server's local bundle, format it, and submit it to the contract.

    Args:
        server_num: server number whose local bundle to publish.
        verb: "post" for first publish, "put" for upsert (addition/rotation).

    Returns:
        (status_code, response_text) tuple.
    """
    td = spire_utils.trust_domain(server_num)
    bundle = print_bundle(server_num)
    formatted = format_bundle(td, bundle)
    if verb == "post":
        status, text = post_bundle(formatted)
    elif verb == "put":
        status, text = upsert_bundle(formatted)
    else:
        raise ValueError(f"verb must be 'post' or 'put', got {verb!r}")
    print(f"{verb}_bundle for server {server_num}: {status} {text}", file=sys.stderr)
    return status, text
