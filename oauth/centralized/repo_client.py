#!/usr/bin/env python3
"""HTTP client for the OAuth metadata repository (centralized variant)."""

import json
import sys

import requests

REPO_URL = "http://localhost:9080"
FEDERATION_ID = "fed1"


def register(domain_name: str, keycloak_url: str, jwks_uri: str):
    body = {"FederationID": FEDERATION_ID, "Metadata": {
        "DomainName": domain_name,
        "KeycloakURL": keycloak_url,
        "JWKSURL": jwks_uri,
    }}
    r = requests.post(
        f"{REPO_URL}/metadata/register",
        params={"federation_id": FEDERATION_ID},
        json=body,
        timeout=10,
    )
    print(f"register {domain_name}: {r.status_code} {r.text}", file=sys.stderr)
    r.raise_for_status()


def delete(domain_name: str):
    body = {"FederationID": FEDERATION_ID, "DomainName": domain_name}
    r = requests.delete(f"{REPO_URL}/metadata", json=body, timeout=10)
    print(f"delete {domain_name}: {r.status_code} {r.text}", file=sys.stderr)
    r.raise_for_status()


def notify_key_rotated(domain_name: str):
    body = {"FederationID": FEDERATION_ID, "DomainName": domain_name}
    r = requests.post(f"{REPO_URL}/metadata/key-rotated", json=body, timeout=10)
    r.raise_for_status()


def list_metadata():
    r = requests.get(f"{REPO_URL}/metadata", params={"federation_id": FEDERATION_ID}, timeout=10)
    r.raise_for_status()
    return r.json().get("Metadata", [])


def open_event_stream(timeout=None):
    r = requests.get(f"{REPO_URL}/events", stream=True, timeout=timeout)
    r.raise_for_status()
    return r


def iter_events(response):
    for line in response.iter_lines():
        if not line:
            continue
        line = line.decode("utf-8") if isinstance(line, bytes) else line
        if not line.startswith("data: "):
            continue
        try:
            yield json.loads(line[6:])
        except json.JSONDecodeError as e:
            print(f"[repo_client] event parse error: {e}", file=sys.stderr)


def stream_events(timeout=None):
    yield from iter_events(open_event_stream(timeout=timeout))
