#!/usr/bin/env python3
"""Helpers used when a server removes itself from the federation."""

import os
import sys

import _bootstrap  # noqa: F401  (sys.path side effect)
import spire_utils


def _parse_entries(entry_output):
    entries = []
    current = {}
    for line in entry_output.split("\n"):
        if line.startswith("Entry ID"):
            if current:
                entries.append(current)
            current = {"entry_id": line.split(":", 1)[1].strip() if ":" in line else ""}
        elif "SPIFFE ID" in line and ":" in line:
            current["spiffe_id"] = line.split(":", 1)[1].strip()
        elif "Parent ID" in line and ":" in line:
            current["parent_id"] = line.split(":", 1)[1].strip()
    if current and "entry_id" in current:
        entries.append(current)
    return entries


def clean_local_entries(my_num):
    """Strip every federatesWith relationship from this server's registration entries.

    Lists all entries via `spire-server entry show`, then re-issues
    `entry update` for each without `-federatesWith`, which removes the
    federation trust. Used during member self-removal so the departing
    server stops vouching for peers.
    """
    entries = _parse_entries(spire_utils.spire_server("entry", "show", server_num=my_num))
    print(f"Found {len(entries)} entries to update", file=sys.stderr)

    user_selector = f"unix:user:{os.environ.get('USER', 'root')}"
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
            "-selector", user_selector,
            server_num=my_num,
        )

    print(f"Removed federation trust from all registration entries on server {my_num}", file=sys.stderr)
