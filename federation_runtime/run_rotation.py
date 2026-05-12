#!/usr/bin/env python3
"""Rotate X.509 authority for a server and propagate the new bundle."""

import sys
import time

import _bootstrap  # noqa: F401  (sys.path side effect)
import spire_utils

import repo_client
import epoch_io
from orchestration import poll_until
from measure_rotation_end import measure_rotation_end


def _epoch_path(num, name):
    return spire_utils.server_dir(num) / f"{name}.epoch"


def record_rotation_start(num):
    epoch_io.write_epoch(_epoch_path(num, "rotation_start"))
    epoch_io.clear_epoch(_epoch_path(num, "rotation_end"))


def record_rotation_end(num):
    epoch_io.write_epoch(_epoch_path(num, "rotation_end"))


def record_event_fired(num):
    epoch_io.write_epoch(_epoch_path(num, "event_fired"))


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
        server_num=num,
    )


def taint_x509_authority(num, authority_id):
    spire_utils.spire_server(
        "localauthority", "x509", "taint",
        "-authorityID", authority_id,
        server_num=num,
    )


def rotate_key_for_server(num, max_server):
    """Rotate X.509 authority for a server and broadcast the new bundle.

    Args:
        num: server number to rotate.
        max_server: max server number in the federation (used by the
            measurement script to know which peers to poll).
    """
    record_rotation_start(num)

    active_auth_id = get_active_x509_authority_id(num)
    prepared_auth_id = prepare_new_x509_authority(num)
    print(f"active: {active_auth_id}, prepared: {prepared_auth_id}", file=sys.stderr)

    activate_x509_authority(num, prepared_auth_id)
    taint_x509_authority(num, active_auth_id)
    time.sleep(1)

    repo_client.publish_bundle_for_server(num, "put")
    record_rotation_end(num)
    record_event_fired(num)

    print("Polling for propagation completion...", file=sys.stderr)
    poll_until(measure_rotation_end, num, max_server, sleep=1)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: run_rotation.py <num> <max_server>", file=sys.stderr)
        sys.exit(1)
    rotate_key_for_server(int(sys.argv[1]), int(sys.argv[2]))
