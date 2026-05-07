#!/usr/bin/env python3
"""Measure experiment end time for key rotation."""

import sys
from pathlib import Path
import re
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "common"))
import spire_utils

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
                if ts:
                    if latest_rotation_ts is None or ts > latest_rotation_ts:
                        latest_rotation_ts = ts
                        rotated_num = server_num
        except Exception:
            pass

    if rotated_num is None:
        raise RuntimeError("Could not auto-detect rotated server (no rotation log entries found)")

    return rotated_num


def collect_peer_log_files(workloads_dir, skip_dirs):
    log_files = []
    for log_file in workloads_dir.glob("*/*/workload.log"):
        if log_file.parent.parent.name not in skip_dirs:
            log_files.append(log_file)
    return log_files


def compute_rotation_timing(rotated_num):
    # rotation_duration: server-side rotation work on the rotated server only.
    # start = just before `localauthority x509 prepare`; end = just after the new
    # bundle is PUT to the centralized repo. Covers prepare + activate + taint +
    # a 1s hardcoded sleep + repo push. Excludes peer fetch/apply and workload
    # re-handshake (those land in communication_duration).
    rotation_start_file = spire_utils.server_dir(rotated_num) / "rotation_start.epoch"
    rotation_end_file = spire_utils.server_dir(rotated_num) / "rotation_end.epoch"

    if not (rotation_start_file.exists() and rotation_end_file.exists()):
        return {}

    rotation_start_epoch = float(rotation_start_file.read_text().strip())
    rotation_end_epoch = float(rotation_end_file.read_text().strip())
    rotation_duration = rotation_end_epoch - rotation_start_epoch

    rotation_start_human = datetime.fromtimestamp(rotation_start_epoch).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    rotation_end_human = datetime.fromtimestamp(rotation_end_epoch).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

    print(f"rotation_start         = {rotation_start_human}")
    print(f"rotation_end           = {rotation_end_human}")
    print(f"rotation_duration      = {rotation_duration:.6f}s")

    return {
        "start": rotation_start_human,
        "end": rotation_end_human,
        "duration": rotation_duration,
    }


def compute_propagation_timing(rotated_num, server_count):
    rotated_td = spire_utils.trust_domain(rotated_num)
    event_fired_file = spire_utils.server_dir(rotated_num) / "event_fired.epoch"

    if not event_fired_file.exists():
        raise RuntimeError(f"event_fired.epoch not found for server {rotated_num}")

    event_fired_epoch = float(event_fired_file.read_text().strip())

    # Collect bundle_applied timestamps from all peer listeners
    bundle_applied_epochs = []
    for i in range(1, server_count + 1):
        if i == rotated_num:
            continue

        listener_log = spire_utils.server_dir(i) / "listener.log"
        if not listener_log.exists():
            raise RuntimeError(f"listener.log not found for server {i}")

        peer_epoch = None
        content = listener_log.read_text()
        for line in content.split('\n'):
            if f"bundle_applied {rotated_td}" in line:
                parts = line.split()
                if len(parts) >= 3:
                    try:
                        candidate = float(parts[-1])
                        if candidate >= event_fired_epoch:
                            peer_epoch = candidate
                    except ValueError:
                        pass

        if peer_epoch is None:
            raise RuntimeError(f"fresh bundle_applied {rotated_td} not yet logged for server {i}")
        bundle_applied_epochs.append(peer_epoch)

    max_applied_epoch = max(bundle_applied_epochs)
    propagation_duration = max_applied_epoch - event_fired_epoch

    event_fired_human = datetime.fromtimestamp(event_fired_epoch).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    max_applied_human = datetime.fromtimestamp(max_applied_epoch).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

    print(f"event_fired            = {event_fired_human}")
    print(f"bundle_applied (last)  = {max_applied_human}")
    print(f"propagation_duration   = {propagation_duration:.6f}s")

    return {
        "event_fired": event_fired_human,
        "bundle_applied_last": max_applied_human,
        "duration": propagation_duration,
    }


def compute_full_mesh_timing(rotated_num, server_count):
    event_fired_file = spire_utils.server_dir(rotated_num) / "event_fired.epoch"

    if not event_fired_file.exists():
        raise RuntimeError(f"event_fired.epoch not found for server {rotated_num}")

    event_fired_epoch = float(event_fired_file.read_text().strip())

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
            for line in log_file.read_text().split('\n'):
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
    full_mesh_duration = max_epoch - event_fired_epoch

    event_fired_human = datetime.fromtimestamp(event_fired_epoch).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    full_mesh_end_human = datetime.fromtimestamp(max_epoch).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

    print(f"full_mesh_end          = {full_mesh_end_human}")
    print(f"full_mesh_duration     = {full_mesh_duration:.6f}s")

    return {
        "event_fired": event_fired_human,
        "full_mesh_end": full_mesh_end_human,
        "duration": full_mesh_duration,
    }


def measure_rotation_end(rotated_num=None, server_count=None):
    """
    Find rotation and propagation times across all servers.

    Args:
        rotated_num: server number that was rotated. If None, auto-detect.
        server_count: total servers in federation. If None, infer from workloads dir.

    Returns:
        dict with rotation and propagation times

    Raises:
        RuntimeError if timing files not found
    """
    workloads_dir = spire_utils.artefacts_dir() / "workloads"

    if not workloads_dir.exists():
        raise RuntimeError(f"Workloads directory not found: {workloads_dir}")

    if rotated_num is None:
        rotated_num = auto_detect_rotated_server(workloads_dir)
    if server_count is None:
        server_count = len(list(workloads_dir.glob("*/")))

    rotation_info = compute_rotation_timing(rotated_num)
    propagation_info = compute_propagation_timing(rotated_num, server_count)
    full_mesh_info = compute_full_mesh_timing(rotated_num, server_count)

    return {
        "rotated_num": rotated_num,
        "rotation": rotation_info,
        "propagation": propagation_info,
        "full_mesh": full_mesh_info,
    }

if __name__ == "__main__":
    rotated_num = int(sys.argv[1]) if len(sys.argv) > 1 else None
    server_count = int(sys.argv[2]) if len(sys.argv) > 2 else None
    try:
        measure_rotation_end(rotated_num, server_count)
    except RuntimeError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        sys.exit(1)
