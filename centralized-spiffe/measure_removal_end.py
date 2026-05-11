#!/usr/bin/env python3
"""Measure experiment end time for member removal."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "common"))
import spire_utils

sys.path.insert(0, str(Path(__file__).parent))
import epoch_io
from orchestration import scan_listener_log_for_marker


def compute_propagation_timing(removed_num, server_count):
    """Time from removal_start to the last peer logging bundle_deleted.

    Raises RuntimeError if timing not available yet (used by pollers).
    """
    removed_td = spire_utils.trust_domain(removed_num)
    removal_start_file = spire_utils.server_dir(removed_num) / "removal_start.epoch"
    if not removal_start_file.exists():
        raise RuntimeError(f"removal_start.epoch not found for server {removed_num}")

    removal_start_epoch = epoch_io.read_epoch(removal_start_file)

    bundle_deleted_epochs = []
    for i in range(1, server_count + 1):
        if i == removed_num:
            continue
        peer_epoch = scan_listener_log_for_marker(i, "bundle_deleted", removed_td, removal_start_epoch)
        if peer_epoch is None:
            raise RuntimeError(f"fresh bundle_deleted {removed_td} not yet logged for server {i}")
        bundle_deleted_epochs.append(peer_epoch)

    max_deleted_epoch = max(bundle_deleted_epochs)
    duration = max_deleted_epoch - removal_start_epoch
    removal_start_human = epoch_io.human(removal_start_epoch)
    max_deleted_human = epoch_io.human(max_deleted_epoch)

    print(f"removal_start          = {removal_start_human}")
    print(f"bundle_deleted (last)  = {max_deleted_human}")
    print(f"propagation_duration   = {duration:.6f}s")

    return {
        "removal_start": removal_start_human,
        "bundle_deleted_last": max_deleted_human,
        "duration": duration,
    }


def compute_zero_communication_timing(removed_num):
    """Time from removal_start to the last periodic_send_success from the removed server.

    Raises RuntimeError if timing not available yet (used by pollers).
    """
    removal_start_file = spire_utils.server_dir(removed_num) / "removal_start.epoch"
    if not removal_start_file.exists():
        raise RuntimeError(f"removal_start.epoch not found for server {removed_num}")

    removal_start_epoch = epoch_io.read_epoch(removal_start_file)

    workload_dir = spire_utils.workload_dir(removed_num)
    zero_comm_markers = sum(
        1 for log in sorted(workload_dir.glob("*/workload.log"))
        if "zero_communication_achieved" in log.read_text()
    )
    if zero_comm_markers != 4:
        raise RuntimeError(f"zero_communication_achieved marker found in {zero_comm_markers}/4 workload logs")

    last_success_epoch = None
    for workload_log in workload_dir.glob("*/workload.log"):
        for line in workload_log.read_text().split("\n"):
            if "periodic_send_success" not in line:
                continue
            ts = spire_utils.parse_timestamp(line)
            if not ts:
                continue
            epoch = spire_utils.epoch_from_log_ts(ts)
            if epoch >= removal_start_epoch and (last_success_epoch is None or epoch > last_success_epoch):
                last_success_epoch = epoch

    if last_success_epoch is None:
        raise RuntimeError(f"no periodic_send_success found in workload logs for server {removed_num}")

    duration = last_success_epoch - removal_start_epoch
    removal_start_human = epoch_io.human(removal_start_epoch)
    last_success_human = epoch_io.human(last_success_epoch)

    print(f"removal_start          = {removal_start_human}")
    print(f"last_periodic_success  = {last_success_human}")
    print(f"zero_communication_duration = {duration:.6f}s")

    return {
        "removal_start": removal_start_human,
        "last_success": last_success_human,
        "duration": duration,
    }


def measure_removal_end(removed_num, server_count):
    """Compute propagation and zero-communication durations for member removal.

    Raises RuntimeError if timing files not found (used by pollers).
    """
    return {
        "removed_num": removed_num,
        "propagation": compute_propagation_timing(removed_num, server_count),
        "zero_communication": compute_zero_communication_timing(removed_num),
    }


if __name__ == "__main__":
    removed_num = int(sys.argv[1]) if len(sys.argv) > 1 else None
    server_count = int(sys.argv[2]) if len(sys.argv) > 2 else None
    if removed_num is None or server_count is None:
        print("Usage: measure_removal_end.py <removed_num> <server_count>", file=sys.stderr)
        sys.exit(1)
    try:
        measure_removal_end(removed_num, server_count)
    except RuntimeError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        sys.exit(1)
