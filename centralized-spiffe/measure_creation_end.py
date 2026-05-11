#!/usr/bin/env python3
"""Measure federation creation duration.

What this measures:
  START : moment the first cluster's bundle is posted to the centralized
          repository (recorded by `record_creation_start` into
          artefacts/creation_start.epoch).
  END   : highest timestamp of the "All messages sent, experiemnt is finished"
          log line across all n*4 workloads.

What "All messages sent" means (see src/example-workload/main.go):
  Each workload dials every workload in every OTHER cluster
  (4 ports * (n-1) servers) via spiffetls. The marker is logged after
  wg.Wait() returns, i.e. after every dial completed successfully.
  - Each dial requires a successful mTLS handshake, which in turn requires
    both peers to validate each other's cert against the federated bundles.
  - Each workload then sends a ping (one-way write); the pong response is
    NOT awaited (response read is commented out in main.go).
  So "All messages sent" implies bidirectional cert-trust works, and that
  every cross-cluster pair completed the TLS handshake. It does not imply
  application-level pong reception.

Duration therefore captures: bundle propagation + federation setup +
registration entry distribution + workload SVID issuance + cross-cluster
mTLS handshake convergence for every workload pair.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "common"))
import spire_utils

sys.path.insert(0, str(Path(__file__).parent))
import epoch_io


def record_creation_start():
    """Record the moment the first bundle is about to be posted."""
    epoch_io.write_epoch(spire_utils.artefacts_dir() / "creation_start.epoch")


def measure_creation_end(n):
    """Compute duration from creation_start.epoch to last "All messages sent" line.

    Args:
        n: number of servers.

    Returns:
        (start_human, end_ts, duration_s) tuple.

    Raises:
        RuntimeError if markers/file not found or count mismatch (used by pollers).
    """
    workloads_dir = spire_utils.artefacts_dir() / "workloads"
    if not workloads_dir.exists():
        raise RuntimeError(f"Workloads directory not found: {workloads_dir}")

    creation_start_file = spire_utils.artefacts_dir() / "creation_start.epoch"
    if not creation_start_file.exists():
        raise RuntimeError(f"creation_start.epoch not found: {creation_start_file}")

    log_files = []
    for i in range(1, n + 1):
        server_dir = workloads_dir / str(i)
        if not server_dir.exists():
            raise RuntimeError(f"Server directory not found: {server_dir}")
        log_files.extend(server_dir.glob("*/workload.log"))

    end_marker = "All messages sent, experiemnt is finished"
    never_match = "\x00__never_match__\x00"

    _, highest_end, match_count = spire_utils.highest_and_lowest_timestamps(
        log_files, never_match, end_marker,
    )

    expected = n * 4
    if match_count != expected:
        raise RuntimeError(
            f"end-marker count mismatch: got {match_count}, expected {expected} ({n} servers * 4 workloads)"
        )
    if highest_end is None:
        raise RuntimeError("Missing end timestamp")

    start_epoch = epoch_io.read_epoch(creation_start_file)
    end_epoch = spire_utils.epoch_from_log_ts(highest_end)
    duration = end_epoch - start_epoch
    start_human = epoch_io.human(start_epoch)

    print(f"start    = {start_human}")
    print(f"end      = {highest_end}")
    print(f"duration = {duration:.6f}s")

    return start_human, highest_end, duration


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: measure_creation_end.py <n>", file=sys.stderr)
        sys.exit(1)
    try:
        measure_creation_end(int(sys.argv[1]))
    except RuntimeError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        sys.exit(1)
