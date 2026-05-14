#!/usr/bin/env python3
"""Web3 client for the OAuthMetadataStore contract.

Exposes the same surface as `centralized/repo_client.py` so the listener
and orchestration scripts work unchanged. The HTTP repo's POST/DELETE/GET/SSE
map onto contract transactions and `eth_getLogs` polling against a local
Hardhat node on http://localhost:8545.
"""

import json
import sys
import time
from pathlib import Path

from web3 import Web3

RPC_URL = "http://localhost:8545"
ABI_PATH = (
    Path(__file__).parent
    / "hardhat"
    / "artifacts"
    / "contracts"
    / "OAuthMetadataStore.sol"
    / "OAuthMetadataStore.json"
)
ADDR_FILE = Path(__file__).parent / "contract_address.txt"
FEDERATION_ID = "fed1"

_w3 = None
_contract_cache = None


def _w3_client():
    global _w3
    if _w3 is None:
        _w3 = Web3(Web3.HTTPProvider(RPC_URL))
    return _w3


def _contract():
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
    tx_hash = fn.transact({"from": _sender()})
    return _w3_client().eth.wait_for_transaction_receipt(tx_hash)


def register(domain_name: str, keycloak_url: str, jwks_uri: str):
    raw = json.dumps({
        "DomainName": domain_name,
        "KeycloakURL": keycloak_url,
        "JWKSURL": jwks_uri,
    })
    try:
        _send(_contract().functions.registerDomain(domain_name, raw))
        print(f"register {domain_name}: 200 ok", file=sys.stderr)
    except Exception as e:
        print(f"register {domain_name}: 500 {e}", file=sys.stderr)
        raise


def delete(domain_name: str):
    try:
        _send(_contract().functions.removeDomain(domain_name))
        print(f"delete {domain_name}: 200 ok", file=sys.stderr)
    except Exception as e:
        print(f"delete {domain_name}: 500 {e}", file=sys.stderr)
        raise


def notify_key_rotated(domain_name: str):
    try:
        _send(_contract().functions.notifyKeyRotated(domain_name))
        print(f"notify_key_rotated {domain_name}: 200 ok", file=sys.stderr)
    except Exception as e:
        print(f"notify_key_rotated {domain_name}: 500 {e}", file=sys.stderr)
        raise


def get_domain(domain_name: str) -> dict:
    raw = _contract().functions.getDomain(domain_name).call()
    return json.loads(raw)


def list_metadata():
    c = _contract()
    limit = 50
    offset = 0
    out = []
    while True:
        names, raws, total = c.functions.getAllDomains(offset, limit).call()
        for _name, raw in zip(names, raws):
            out.append(json.loads(raw))
        if len(out) >= total or not names:
            break
        offset += limit
    return out


def create_event_filters():
    """Snapshot current block number. Call BEFORE backfill."""
    return _w3_client().eth.block_number


def poll_events(from_block, poll_interval=0.1):
    """Yield events using block-range scanning (no expiring filters)."""
    c = _contract()
    w3 = _w3_client()
    last_block = from_block

    while True:
        try:
            current = w3.eth.block_number
            if current > last_block:
                for log_entry in c.events.DomainAdded.get_logs(from_block=last_block + 1, to_block=current):
                    domain_name = log_entry["args"]["domainName"]
                    try:
                        meta = get_domain(domain_name)
                    except Exception:
                        continue
                    yield {
                        "type": "domain_added",
                        "federation_id": FEDERATION_ID,
                        "domain_name": meta["DomainName"],
                        "keycloak_url": meta["KeycloakURL"],
                        "jwks_url": meta["JWKSURL"],
                    }
                for log_entry in c.events.DomainRemoved.get_logs(from_block=last_block + 1, to_block=current):
                    yield {
                        "type": "domain_removed",
                        "federation_id": FEDERATION_ID,
                        "domain_name": log_entry["args"]["domainName"],
                    }
                for log_entry in c.events.KeyRotated.get_logs(from_block=last_block + 1, to_block=current):
                    yield {
                        "type": "key_rotated",
                        "federation_id": FEDERATION_ID,
                        "domain_name": log_entry["args"]["domainName"],
                    }
                last_block = current
        except Exception as e:
            print(f"[repo_client] poll error: {e}, retrying", file=sys.stderr)
        time.sleep(poll_interval)


def stream_events(poll_interval=0.1):
    """Convenience: snapshot block and poll."""
    yield from poll_events(create_event_filters(), poll_interval)
