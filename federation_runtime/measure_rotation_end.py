#!/usr/bin/env python3
"""Measure experiment end time for key rotation."""

import re
import sys

import _bootstrap  # noqa: F401  (sys.path side effect)
import spire_utils
import epoch_io
from orchestration import scan_listener_log_for_marker


def auto_detect_rotated_server(workloads_dir):
    rotation_pattern = re.compile(r'updated for server (\d+)')
    rotated_num = None
    latest_rotation_ts = None

    for log_file in workloads_dir.glob("*/*/workload.log"):
        try:
            content = log_file.read_text()
            for match in rotation_pattern.finditer(content):
                server_num = int(match.group(1))
                start = max(0, content.rfind('\n', 0, match.start()) + 1)
                end = content.find('\n', match.end())
                line = content[start:end]

                ts = spire_utils.parse_timestamp(line)
                if ts and (latest_rotation_ts is None or ts > latest_rotation_ts):
                    latest_rotation_ts = ts
                    rotated_num = server_num
        except Exception:
            pass

    if rotated_num is None:
        raise RuntimeError("Could not auto-detect rotated server (no rotation log entries found)")
    return rotated_num


def compute_rotation_timing(rotated_num):
    """rotation_duration: server-side rotation work on the rotated server only.

    start = just before `localauthority x509 prepare`; end = just after the
    new bundle is published to the variant repo. Covers prepare + activate +
    taint + a 1s hardcoded sleep + repo push. Excludes peer fetch/apply
    and workload re-handshake (those land in full_mesh_duration).
    """
    start_file = spire_utils.server_dir(rotated_num) / "rotation_start.epoch"
    end_file = spire_utils.server_dir(rotated_num) / "rotation_end.epoch"
    if not (start_file.exists() and end_file.exists()):
        return {}

    start_epoch = epoch_io.read_epoch(start_file)
    end_epoch = epoch_io.read_epoch(end_file)
    duration = end_epoch - start_epoch
    start_human = epoch_io.human(start_epoch)
    end_human = epoch_io.human(end_epoch)

    print(f"rotation_start         = {start_human}")
    print(f"rotation_end           = {end_human}")
    print(f"rotation_duration      = {duration:.6f}s")

    return {"start": start_human, "end": end_human, "duration": duration}


def compute_propagation_timing(rotated_num, server_count):
    rotated_td = spire_utils.trust_domain(rotated_num)
    event_fired_file = spire_utils.server_dir(rotated_num) / "event_fired.epoch"
    if not event_fired_file.exists():
        raise RuntimeError(f"event_fired.epoch not found for server {rotated_num}")

    event_fired_epoch = epoch_io.read_epoch(event_fired_file)

    bundle_applied_epochs = []
    for i in range(1, server_count + 1):
        if i == rotated_num:
            continue
        peer_epoch = scan_listener_log_for_marker(i, "bundle_applied", rotated_td, event_fired_epoch)
        if peer_epoch is None:
            raise RuntimeError(f"fresh bundle_applied {rotated_td} not yet logged for server {i}")
        bundle_applied_epochs.append(peer_epoch)

    max_applied_epoch = max(bundle_applied_epochs)
    duration = max_applied_epoch - event_fired_epoch
    event_fired_human = epoch_io.human(event_fired_epoch)
    max_applied_human = epoch_io.human(max_applied_epoch)

    print(f"event_fired            = {event_fired_human}")
    print(f"bundle_applied (last)  = {max_applied_human}")
    print(f"propagation_duration   = {duration:.6f}s")

    return {
        "event_fired": event_fired_human,
        "bundle_applied_last": max_applied_human,
        "duration": duration,
    }


def compute_full_mesh_timing(rotated_num, server_count):
    event_fired_file = spire_utils.server_dir(rotated_num) / "event_fired.epoch"
    if not event_fired_file.exists():
        raise RuntimeError(f"event_fired.epoch not found for server {rotated_num}")
    event_fired_epoch = epoch_io.read_epoch(event_fired_file)

    end_marker = "Finished special communication: communicating again after key rotation"
    workloads_dir = spire_utils.artefacts_dir() / "workloads"

    fresh_epochs = []
    for i in range(1, server_count + 1):
        if i == rotated_num:
            continue
        peer_dir = workloads_dir / str(i)
        if not peer_dir.exists():
            raise RuntimeError(f"workload dir not found for server {i}")
        for log_file in peer_dir.glob("*/workload.log"):
            for line in log_file.read_text().split("\n"):
                if end_marker not in line:
                    continue
                ts = spire_utils.parse_timestamp(line)
                if not ts:
                    continue
                epoch = spire_utils.epoch_from_log_ts(ts)
                if epoch >= event_fired_epoch:
                    fresh_epochs.append(epoch)

    expected = (server_count - 1) * 4
    if len(fresh_epochs) != expected:
        raise RuntimeError(
            f"fresh full-mesh end markers ({len(fresh_epochs)}) != expected ({expected})"
        )

    max_epoch = max(fresh_epochs)
    duration = max_epoch - event_fired_epoch
    event_fired_human = epoch_io.human(event_fired_epoch)
    full_mesh_end_human = epoch_io.human(max_epoch)

    print(f"full_mesh_end          = {full_mesh_end_human}")
    print(f"full_mesh_duration     = {duration:.6f}s")

    return {
        "event_fired": event_fired_human,
        "full_mesh_end": full_mesh_end_human,
        "duration": duration,
    }


def measure_rotation_end(rotated_num=None, server_count=None):
    """Compute rotation, propagation, and full-mesh-rehandshake durations.

    Raises RuntimeError if timing files not found (used by pollers).
    """
    workloads_dir = spire_utils.artefacts_dir() / "workloads"
    if not workloads_dir.exists():
        raise RuntimeError(f"Workloads directory not found: {workloads_dir}")

    if rotated_num is None:
        rotated_num = auto_detect_rotated_server(workloads_dir)
    if server_count is None:
        server_count = len(list(workloads_dir.glob("*/")))

    return {
        "rotated_num": rotated_num,
        "rotation": compute_rotation_timing(rotated_num),
        "propagation": compute_propagation_timing(rotated_num, server_count),
        "full_mesh": compute_full_mesh_timing(rotated_num, server_count),
    }


if __name__ == "__main__":
    rotated_num = int(sys.argv[1]) if len(sys.argv) > 1 else None
    server_count = int(sys.argv[2]) if len(sys.argv) > 2 else None
    try:
        measure_rotation_end(rotated_num, server_count)
    except RuntimeError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        sys.exit(1)
