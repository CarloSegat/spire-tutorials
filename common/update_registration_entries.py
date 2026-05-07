#!/usr/bin/env python3
"""Update all registration entries to include federation trust domains."""

import sys
import os
from pathlib import Path
import re

sys.path.insert(0, str(Path(__file__).parent))
import spire_utils

def list_federation_trust_domains(my_num):
    fed_output = spire_utils.spire_server("federation", "list", server_num=my_num)
    fed_flags = []

    for line in fed_output.split("\n"):
        if line.lstrip().startswith("Trust domain") and ":" in line:
            domain = line.split(":", 1)[1].strip()
            if domain:
                fed_flags.append(f"spiffe://{domain}/spire/server")

    print(f"Found {len(fed_flags)} federation trust domains", file=sys.stderr)
    for td in fed_flags:
        print(f"  {td}", file=sys.stderr)

    return fed_flags


def list_entries(my_num):
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

    return entries


def update_entry(my_num, entry, fed_flags):
    entry_id = entry.get("entry_id", "")
    spiffe_id = entry.get("spiffe_id", "")
    parent_id = entry.get("parent_id", "")

    if not entry_id or not spiffe_id or not parent_id:
        print(f"Skipping incomplete entry: {entry}", file=sys.stderr)
        return

    print(f"Updating entry {entry_id}: {spiffe_id}", file=sys.stderr)

    cmd_args = [
        "entry", "update",
        "-entryID", entry_id,
        "-parentID", parent_id,
        "-spiffeID", spiffe_id,
        "-selector", f"unix:user:{os.environ.get('USER', 'root')}",
    ]

    for td in fed_flags:
        cmd_args.extend(["-federatesWith", td])

    spire_utils.spire_server(*cmd_args, server_num=my_num)


def update_registration_entries(my_num, other_num=None):
    """
    Update all registration entries on a server to include all current federations.

    Args:
        my_num: server number to update
        other_num: (unused, kept for compat with shell version)
    """
    fed_flags = list_federation_trust_domains(my_num)
    entries = list_entries(my_num)

    for entry in entries:
        update_entry(my_num, entry, fed_flags)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: update_registration_entries.py <my_num> [other_num]", file=sys.stderr)
        sys.exit(1)

    my_num = int(sys.argv[1])
    other_num = int(sys.argv[2]) if len(sys.argv) > 2 else None
    update_registration_entries(my_num, other_num)
