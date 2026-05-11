#!/usr/bin/env python3
"""Read/write the .epoch sentinel files used to measure experiment phases.

Each phase of an experiment (creation_start, addition_start,
rotation_start, rotation_end, event_fired, removal_start) drops a single
file containing one float-encoded Unix timestamp. The four
measure_*_end.py scripts read these back, subtract, and report the
durations that feed the paper's plots.
"""

import time
from datetime import datetime
from pathlib import Path


def write_epoch(path, ts=None):
    """Write a single Unix timestamp to `path`.

    Creates parent directories if needed. Used at the start/end of each
    measured phase.

    Args:
        path: file path to write.
        ts: timestamp to record (defaults to current time).
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(ts if ts is not None else time.time()))


def read_epoch(path):
    """Read a Unix timestamp from a previously written epoch file.

    Args:
        path: file path to read.

    Returns:
        float epoch timestamp.
    """
    return float(Path(path).read_text().strip())


def human(epoch):
    """Format a Unix timestamp as `YYYY-MM-DD HH:MM:SS.mmm` for log output."""
    return datetime.fromtimestamp(epoch).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def clear_epoch(path):
    """Remove an epoch file if it exists.

    Used to invalidate a stale `*_end.epoch` before a new measurement so
    pollers don't read a previous run's value.
    """
    Path(path).unlink(missing_ok=True)
