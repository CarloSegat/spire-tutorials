#!/usr/bin/env python3
"""Shared SPIRE utilities. No third-party deps (stdlib only)."""

import subprocess
import sys
from pathlib import Path
import re
from datetime import datetime
import os
import time

def base_dir():
    """Return repo root by walking up from this file."""
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / "CLAUDE.md").exists() and "spire-tutorials" in str(current):
            return current
        current = current.parent
    raise RuntimeError("Could not find spire-tutorials repo root")

def artefacts_dir():
    return base_dir() / "artefacts"

def server_sock(n):
    return artefacts_dir() / "server" / str(n) / "api.sock"

def server_dir(n):
    return artefacts_dir() / "server" / str(n)

def workload_dir(n, w=None):
    if w is None:
        return artefacts_dir() / "workloads" / str(n)
    return artefacts_dir() / "workloads" / str(n) / str(w)

def fed_port(n):
    """Federation port for server n: 8082 + 1 + (n * 6 - 5)."""
    return 8082 + 1 + (n * 6 - 5)

def trust_domain(n):
    return f"{n}.snet.example"

def run(cmd, check=True, capture_output=False, echo=False):
    """
    Wrapper around subprocess.run.

    Args:
        cmd: list of command args
        check: raise on nonzero exit (default True)
        capture_output: return stdout as string (default False)
        echo: print cmd before running (default False)

    Returns:
        stdout string if capture_output=True, else CompletedProcess
    """
    if echo:
        print(" ".join(str(c) for c in cmd), file=sys.stderr)

    result = subprocess.run(
        cmd,
        check=check,
        capture_output=capture_output,
        text=True
    )

    if capture_output:
        return result.stdout.strip()
    return result

def spire_server(*args, server_num):
    """
    Run spire-server command for a specific server.

    Args:
        *args: command arguments (e.g., "bundle", "show")
        server_num: server number

    Returns:
        stdout string
    """
    cmd = [
        str(artefacts_dir() / "bin" / "spire-server"),
        *args,
        "-socketPath",
        str(server_sock(server_num))
    ]
    return run(cmd, capture_output=True)

def parse_timestamp(line):
    """Extract time="YYYY-MM-DD HH:MM:SS.ffffff" from a workload log line."""
    match = re.search(r'time="([^"]*)"', line)
    return match.group(1) if match else None

def epoch_from_log_ts(ts_str):
    """
    Convert "YYYY-MM-DD HH:MM:SS.ffffff" to float epoch.
    Handles both base and fractional parts.
    """
    if "." in ts_str:
        base, frac = ts_str.rsplit(".", 1)
    else:
        base, frac = ts_str, "0"

    dt = datetime.strptime(base, "%Y-%m-%d %H:%M:%S")
    epoch = dt.timestamp()

    # Append fractional seconds
    frac_float = float("0." + frac)
    return epoch + frac_float

def highest_and_lowest_timestamps(log_files, start_marker, end_marker, skip_dirs=None):
    """
    Scan log files for start/end markers and return (lowest_start, highest_end, count).

    Args:
        log_files: iterable of Path objects
        start_marker: string to match for start
        end_marker: string to match for end
        skip_dirs: set of directory names to skip (for measure_rotation_end)

    Returns:
        (lowest_start_ts, highest_end_ts, end_count) tuple

    Raises:
        RuntimeError: if no markers found or other issues
    """
    if skip_dirs is None:
        skip_dirs = set()

    lowest_start = None
    highest_end = None
    end_count = 0

    for log_path in log_files:
        # Skip if server dir (workloads/<server>/<workload>/workload.log) is in skip_dirs
        if log_path.parent.parent.name in skip_dirs:
            continue

        if not log_path.is_file():
            continue

        try:
            with open(log_path, "r") as f:
                for line in f:
                    ts = parse_timestamp(line)
                    if not ts:
                        continue

                    if start_marker in line:
                        if lowest_start is None or ts < lowest_start:
                            lowest_start = ts

                    if end_marker in line:
                        end_count += 1
                        if highest_end is None or ts > highest_end:
                            highest_end = ts
        except Exception as e:
            raise RuntimeError(f"Error reading {log_path}: {e}")

    return lowest_start, highest_end, end_count
