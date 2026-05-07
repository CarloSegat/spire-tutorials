#!/usr/bin/env python3
"""Rotate X.509 authority for a server and propagate the new bundle."""

import json
import sys
import time
from pathlib import Path
import tempfile
import requests

sys.path.insert(0, str(Path(__file__).parent.parent / "common"))
import spire_utils
from print_bundle import print_bundle
from format_bundle import format_bundle
from update_bundle import update_bundle

sys.path.insert(0, str(Path(__file__).parent))
from measure_rotation_end import measure_rotation_end

def record_rotation_start(num):
    rotation_start_file = spire_utils.server_dir(num) / "rotation_start.epoch"
    rotation_start_file.write_text(str(time.time()))

    rotation_end_file = spire_utils.server_dir(num) / "rotation_end.epoch"
    if rotation_end_file.exists():
        rotation_end_file.unlink()


def record_rotation_end(num):
    rotation_end_file = spire_utils.server_dir(num) / "rotation_end.epoch"
    rotation_end_file.write_text(str(time.time()))


def record_event_fired(num):
    event_fired_file = spire_utils.server_dir(num) / "event_fired.epoch"
    event_fired_file.write_text(str(time.time()))


def get_active_x509_authority_id(num):
    output = spire_utils.spire_server("localauthority", "x509", "show", server_num=num)

    in_active_block = False
    for line in output.split("\n"):
        if line.startswith("Active X.509 authority:"):
            in_active_block = True
            continue
        if in_active_block and ("Prepared X.509 authority:" in line or "Old X.509 authority:" in line):
            in_active_block = False
        if in_active_block and "Authority ID:" in line:
            return line.split("Authority ID:")[1].strip()
    return None


def prepare_new_x509_authority(num):
    output = spire_utils.spire_server("localauthority", "x509", "prepare", server_num=num)

    for line in output.split("\n"):
        if "Authority ID:" in line:
            return line.split("Authority ID:")[1].strip()
    return None


def activate_x509_authority(num, authority_id):
    spire_utils.spire_server(
        "localauthority", "x509", "activate",
        "-authorityID", authority_id,
        server_num=num
    )


def taint_x509_authority(num, authority_id):
    spire_utils.spire_server(
        "localauthority", "x509", "taint",
        "-authorityID", authority_id,
        server_num=num
    )


def update_bundle_in_centralized_repo(num):
    td = spire_utils.trust_domain(num)
    bundle = print_bundle(num)
    formatted = format_bundle(td, bundle)
    status, response = update_bundle(formatted)
    print(f"update_bundle response: {status} {response}", file=sys.stderr)


def fetch_bundles_from_centralized_repo():
    response = requests.get("http://localhost:8080/bundles/test")
    response.raise_for_status()
    repo_data = response.json()

    repo_trust_domains = set()
    bundle_data = {}
    for bundle in repo_data.get("QualifiedBundles", []):
        td = bundle["TrustDomainName"]
        repo_trust_domains.add(td)
        bundle_data[td] = bundle["RawBundle"]

    return repo_trust_domains, bundle_data


def get_current_federations_on_peer(server_num):
    fed_output = spire_utils.spire_server("federation", "list", server_num=server_num)
    current_feds = set()
    for line in fed_output.split("\n"):
        if line.lstrip().startswith("Trust domain") and ":" in line:
            domain = line.split(":", 1)[1].strip()
            if domain:
                current_feds.add(domain)
    return current_feds


def delete_stale_federations(peer_num, current_feds, repo_trust_domains):
    for fed in current_feds:
        if fed == spire_utils.trust_domain(peer_num):
            continue
        if fed not in repo_trust_domains:
            print(f"Member {fed} has left, removing from server {peer_num}", file=sys.stderr)
            spire_utils.spire_server(
                "federation", "delete",
                "-id", fed,
                server_num=peer_num
            )


def set_rotated_bundle_on_peer(peer_num, rotated_num, bundle_data):
    rotated_td = spire_utils.trust_domain(rotated_num)
    if rotated_td not in bundle_data:
        return

    print(f"Setting bundle for {rotated_td} on server {peer_num}", file=sys.stderr)

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write(bundle_data[rotated_td])
        temp_path = f.name

    try:
        spire_utils.spire_server(
            "bundle", "set",
            "-id", rotated_td,
            "-path", temp_path,
            "-format", "spiffe",
            server_num=peer_num
        )
    finally:
        Path(temp_path).unlink()


def poll_until_propagation_finishes(num, max_server):
    print(f"Polling for propagation completion...", file=sys.stderr)
    while True:
        try:
            measure_rotation_end(rotated_num=num, server_count=max_server)
            break
        except RuntimeError:
            time.sleep(1)


def rotate_key_for_server(num, max_server):
    """
    Rotate X.509 authority for a server and broadcast new bundle via SSE.

    Args:
        num: server number to rotate
        max_server: max server number (for iteration)
    """
    record_rotation_start(num)

    active_auth_id = get_active_x509_authority_id(num)
    prepared_auth_id = prepare_new_x509_authority(num)
    print(f"active: {active_auth_id}, prepared: {prepared_auth_id}", file=sys.stderr)

    activate_x509_authority(num, prepared_auth_id)
    taint_x509_authority(num, active_auth_id)
    time.sleep(1)

    update_bundle_in_centralized_repo(num)
    record_rotation_end(num)
    record_event_fired(num)

    poll_until_propagation_finishes(num, max_server)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: 3_rotate_key.py <num> <max_server>", file=sys.stderr)
        sys.exit(1)

    num = int(sys.argv[1])
    max_server = int(sys.argv[2]) if len(sys.argv) > 2 else None

    if max_server is None:
        print("Error: max_server required", file=sys.stderr)
        sys.exit(1)

    rotate_key_for_server(num, max_server)
