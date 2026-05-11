#!/usr/bin/env python3
"""Shared orchestration helpers for the experiment driver scripts.

Each numbered driver (1_run_creation, 2_run_addition, 3_rotate_key,
4_run_removal) repeats the same handful of moves: spawn the per-server
SSE listener, busy-poll a measure_*_end function until the experiment
markers are present, scan listener logs for a marker emitted by a peer,
and apply a freshly fetched bundle to a local SPIRE server. Those moves
live here.
"""

import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "common"))
import spire_utils

LISTENER_SCRIPT = Path(__file__).parent / "listen_and_react.py"


def poll_until(measure_fn, *args, sleep=2, on_success=None, on_retry=None):
    """Repeatedly call `measure_fn(*args)` until it stops raising RuntimeError.

    Used to wait for an experiment's end markers to appear in the
    workload/listener logs. Returns whatever the measure function
    returns once it succeeds.

    Args:
        measure_fn: callable that raises RuntimeError while not ready.
        *args: positional args forwarded to measure_fn.
        sleep: seconds to wait between attempts.
        on_success: optional callback invoked with the result.
        on_retry: optional callback invoked with the RuntimeError each retry.
    """
    while True:
        try:
            result = measure_fn(*args)
            if on_success is not None:
                on_success(result)
            return result
        except RuntimeError as e:
            if on_retry is not None:
                on_retry(e)
            time.sleep(sleep)


def start_listener(server_num, max_server):
    """Spawn listen_and_react.py as a detached subprocess for `server_num`.

    The listener subscribes to the repo's SSE stream and reacts to
    bundle_updated / bundle_deleted events for this server.

    Returns:
        the subprocess.Popen handle (output discarded).
    """
    return subprocess.Popen(
        [
            "python3",
            str(LISTENER_SCRIPT),
            "--server-num", str(server_num),
            "--max-server", str(max_server),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def get_max_server_number():
    """Return the highest server number currently present under artefacts/server/.

    Returns 0 if the directory exists but has no numbered child. Used to
    auto-detect the next server number for addition and the federation
    size for listener spawning.
    """
    server_dir = spire_utils.artefacts_dir() / "server"
    if not server_dir.exists():
        return 0

    max_n = 0
    for d in server_dir.iterdir():
        if not d.is_dir():
            continue
        try:
            n = int(d.name)
        except ValueError:
            continue
        if n > max_n:
            max_n = n
    return max_n


def scan_listener_log_for_marker(server_num, marker, td, since_epoch):
    """Find the latest epoch a peer's listener logged a given marker for a trust domain.

    Listener log lines have shape `<epoch> <marker> <trust_domain> <event_epoch>`
    (see listen_and_react.log_event). This scans the file for the marker
    matching `td` whose trailing epoch token is >= `since_epoch` and
    returns the most recent such epoch. Used by the rotation and removal
    measurement scripts to compute propagation duration.

    Args:
        server_num: peer server number whose listener.log to scan.
        marker: e.g. "bundle_applied" or "bundle_deleted".
        td: the trust domain string being awaited.
        since_epoch: floor (in seconds) to filter stale matches from prior runs.

    Returns:
        latest matching epoch as float, or None if no fresh match yet.
    """
    listener_log = spire_utils.server_dir(server_num) / "listener.log"
    if not listener_log.exists():
        raise RuntimeError(f"listener.log not found for server {server_num}")

    needle = f"{marker} {td}"
    latest = None
    for line in listener_log.read_text().split("\n"):
        if needle not in line:
            continue
        parts = line.split()
        if len(parts) < 3:
            continue
        try:
            candidate = float(parts[-1])
        except ValueError:
            continue
        if candidate >= since_epoch:
            latest = candidate
    return latest


def apply_raw_bundle(td, raw_bundle, server_num):
    """Write a raw bundle string to a tempfile and feed it to `spire-server bundle set`.

    Used by both the SSE listener (on bundle_updated) and the rotation
    orchestrator (when pushing a freshly rotated bundle to peers).
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tf:
        tf.write(raw_bundle)
        tmp_path = tf.name
    try:
        spire_utils.spire_server(
            "bundle", "set",
            "-id", td,
            "-path", tmp_path,
            "-format", "spiffe",
            server_num=server_num,
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)
