#!/usr/bin/env python3
"""HTTP client for the centralized bundle repository.

The centralized-spiffe binary exposes a small REST API on localhost:8080
for member SPIRE servers to publish their trust-bundles, fetch the
federation-wide bundle set, and subscribe to update/delete events via SSE.
This module is the single place those endpoints are spoken to.
"""

import json
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent / "common"))
import spire_utils
from print_bundle import print_bundle
from format_bundle import format_bundle

REPO_URL = "http://localhost:8080"
FEDERATION_ID = "test"


def _as_json(formatted):
    return json.loads(formatted) if isinstance(formatted, str) else formatted


def post_bundle(formatted):
    """POST a formatted bundle to the repo (initial publish, fails if it exists).

    Args:
        formatted: JSON string or dict with FederationID and QualifiedBundle.

    Returns:
        (status_code, response_text) tuple.
    """
    r = requests.post(f"{REPO_URL}/bundle", json=_as_json(formatted))
    return r.status_code, r.text


def upsert_bundle(formatted):
    """PUT a formatted bundle to the repo (insert-or-update, used for additions and rotations).

    Args:
        formatted: JSON string or dict with FederationID and QualifiedBundle.

    Returns:
        (status_code, response_text) tuple.
    """
    r = requests.put(f"{REPO_URL}/bundle", json=_as_json(formatted))
    return r.status_code, r.text


def delete_bundle(server_num):
    """DELETE this server's bundle from the repo.

    Triggers a bundle_deleted SSE event that all listeners react to by
    dropping the corresponding trust domain locally. Used during member
    removal.

    Args:
        server_num: server number whose trust domain should be removed.

    Returns:
        (status_code, response_text) tuple.
    """
    td = spire_utils.trust_domain(server_num)
    payload = {"FederationID": FEDERATION_ID, "TrustDomainName": td}
    r = requests.delete(
        f"{REPO_URL}/bundle",
        json=payload,
        headers={"Content-Type": "application/json"},
    )
    print(f"Delete response: {r.status_code} {r.text}", file=sys.stderr)
    return r.status_code, r.text


def get_bundles():
    """GET the full set of qualified bundles currently in the federation.

    Returns:
        List of QualifiedBundle dicts (each has TrustDomainName and RawBundle).
    """
    r = requests.get(f"{REPO_URL}/bundles/{FEDERATION_ID}")
    r.raise_for_status()
    return r.json().get("QualifiedBundles", [])


def stream_events(timeout=None):
    """Subscribe to the repo's SSE event stream.

    Yields each parsed event dict (with `type` and `data` keys) as it
    arrives. Used by listen_and_react.py to react to bundle_updated and
    bundle_deleted events from peers.

    Args:
        timeout: optional request timeout (None = no timeout).
    """
    r = requests.get(f"{REPO_URL}/events", stream=True, timeout=timeout)
    r.raise_for_status()
    for line in r.iter_lines():
        if not line:
            continue
        line = line.decode("utf-8") if isinstance(line, bytes) else line
        if not line.startswith("data: "):
            continue
        try:
            yield json.loads(line[6:])
        except json.JSONDecodeError as e:
            print(f"[repo_client] event parse error: {e}", file=sys.stderr)


def publish_bundle_for_server(server_num, verb):
    """Read this server's local bundle, format it, and publish to the repo.

    Combines the common `trust_domain + print_bundle + format_bundle + send`
    pattern. `verb="post"` is used for the first publish (creation),
    `verb="put"` for republish after addition or rotation.

    Args:
        server_num: server number to publish.
        verb: "post" or "put".

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
