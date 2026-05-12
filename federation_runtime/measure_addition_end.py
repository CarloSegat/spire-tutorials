#!/usr/bin/env python3
"""Measure single-server addition duration.

What this measures:
  START : moment the NEW server's bundle is published to the variant repo
          (recorded by `record_addition_start(n)` into
          artefacts/server/<n>/addition_start.epoch).
  END   : highest timestamp of the "All messages sent, experiemnt is finished"
          log line across the NEW server's 4 workloads only.

Scope (asymmetric on purpose):
  Only the new cluster's 4 workloads are observed. Each of them dials every
  workload in every other (existing) cluster (4 * (n-1) dials per workload).
  See `measure_creation_end.py` for the precise semantics of "All messages
  sent" - same workload binary, same marker.

  Existing clusters' workloads are NOT re-run after addition, so their side
  is not measured here. The mTLS handshake required for each dial is
  bidirectional, so dial success still proves the federation cert-trust
  was correctly established in BOTH directions for every pair involving
  the new cluster.

Duration therefore captures, for the addition flow: bundle propagation +
new-server federation creation + registration entry update + new workloads'
SVID issuance + their cross-cluster mTLS handshake convergence with all
existing workloads.
"""

import sys

import _bootstrap  # noqa: F401  (sys.path side effect)
import spire_utils
import epoch_io


def record_addition_start(n):
    """Record the moment server n's bundle is about to be posted."""
    epoch_io.write_epoch(spire_utils.server_dir(n) / "addition_start.epoch")


def measure_addition_end(n):
    """Compute duration from addition_start.epoch to the new server's "All messages sent" line.

    Raises RuntimeError if markers/file not found or count mismatch (used by pollers).
    """
    workloads_dir = spire_utils.artefacts_dir() / "workloads"
    if not workloads_dir.exists():
        raise RuntimeError(f"Workloads directory not found: {workloads_dir}")

    server_dir = workloads_dir / str(n)
    if not server_dir.exists():
        raise RuntimeError(f"Server directory not found: {server_dir}")

    addition_start_file = spire_utils.server_dir(n) / "addition_start.epoch"
    if not addition_start_file.exists():
        raise RuntimeError(f"addition_start.epoch not found: {addition_start_file}")

    log_files = list(server_dir.glob("*/workload.log"))
    end_marker = "All messages sent, experiemnt is finished"
    never_match = "\x00__never_match__\x00"

    _, highest_end, match_count = spire_utils.highest_and_lowest_timestamps(
        log_files, never_match, end_marker,
    )

    expected = 4
    if match_count != expected:
        raise RuntimeError(
            f"end-marker count mismatch: got {match_count}, expected {expected} (4 workloads)"
        )
    if highest_end is None:
        raise RuntimeError("Missing end timestamp")

    start_epoch = epoch_io.read_epoch(addition_start_file)
    end_epoch = spire_utils.epoch_from_log_ts(highest_end)
    duration = end_epoch - start_epoch
    start_human = epoch_io.human(start_epoch)

    print(f"start    = {start_human}")
    print(f"end      = {highest_end}")
    print(f"duration = {duration:.6f}s")

    return start_human, highest_end, duration


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: measure_addition_end.py <n>", file=sys.stderr)
        sys.exit(1)
    try:
        measure_addition_end(int(sys.argv[1]))
    except RuntimeError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        sys.exit(1)
