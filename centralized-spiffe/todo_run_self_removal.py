#!/usr/bin/env python3
"""Remove a server from the federation."""

import json
import sys
import os
from pathlib import Path
import requests

sys.path.insert(0, str(Path(__file__).parent.parent / "common"))
import spire_utils

def todo_run_self_removal(my_num, max_server=None):
    """
    Remove a server from the federation.

    Deletes the server's bundle from the centralized repo and clears
    federation trust from all its registration entries.

    Args:
        my_num: server number to remove
        max_server: unused, kept for compatibility
    """
    td = spire_utils.trust_domain(my_num)
    federation_id = "test"

    # Delete bundle from centralized repository
    print(f"Deleting bundle for TrustDomainName {td} from FederationID {federation_id}", file=sys.stderr)

    delete_payload = {
        "FederationID": federation_id,
        "TrustDomainName": td,
    }

    response = requests.delete(
        "http://localhost:8080/bundle",
        json=delete_payload,
        headers={"Content-Type": "application/json"}
    )

    print(f"Delete response: {response.status_code} {response.text}", file=sys.stderr)

    # Get all entries and parse them
    entry_output = spire_utils.spire_server("entry", "show", server_num=my_num)

    entries = []
    current_entry = {}

    for line in entry_output.split("\n"):
        if line.startswith("Entry ID"):
            if current_entry:
                entries.append(current_entry)
            current_entry = {"entry_id": line.split(":", 1)[1].strip() if ":" in line else ""}

        elif "SPIFFE ID" in line and ":" in line:
            current_entry["spiffe_id"] = line.split(":", 1)[1].strip()

        elif "Parent ID" in line and ":" in line:
            current_entry["parent_id"] = line.split(":", 1)[1].strip()

    if current_entry and "entry_id" in current_entry:
        entries.append(current_entry)

    print(f"Found {len(entries)} entries to update", file=sys.stderr)

    # Update each entry (without -federatesWith to remove all federation trust)
    for entry in entries:
        entry_id = entry.get("entry_id", "")
        spiffe_id = entry.get("spiffe_id", "")
        parent_id = entry.get("parent_id", "")

        if not entry_id or not spiffe_id or not parent_id:
            print(f"Skipping incomplete entry: {entry}", file=sys.stderr)
            continue

        print(f"Removing federation trust from entry {entry_id} ({spiffe_id})", file=sys.stderr)

        spire_utils.spire_server(
            "entry", "update",
            "-entryID", entry_id,
            "-parentID", parent_id,
            "-spiffeID", spiffe_id,
            "-selector", f"unix:user:{os.environ.get('USER', 'root')}",
            server_num=my_num
        )

    print(f"Removed federation trust from all registration entries on server {my_num}", file=sys.stderr)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: todo_run_self_removal.py <my_num> [max_server]", file=sys.stderr)
        sys.exit(1)

    my_num = int(sys.argv[1])
    max_server = int(sys.argv[2]) if len(sys.argv) > 2 else None

    todo_run_self_removal(my_num, max_server)
