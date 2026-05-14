#!/usr/bin/env python3
"""Shared orchestration helpers for the experiment driver scripts.

Each numbered driver (run_creation, run_addition, run_rotation,
run_removal) repeats the same handful of moves: spawn the per-server
SSE/event listener, busy-poll a measure_*_end function until the
experiment markers are present, scan listener logs for a marker emitted
by a peer, and apply a freshly fetched bundle to a local SPIRE server.
Those moves live here.
"""

import subprocess
import tempfile
import time
from pathlib import Path

import _bootstrap  # noqa: F401  (sys.path side effect)
import spire_utils

LISTENER_SCRIPT = Path(__file__).parent / "listen_and_react.py"


def poll_until(measure_fn, *args, sleep=2, on_success=None, on_retry=None,
               timeout=300):
    """Repeatedly call `measure_fn(*args)` until it stops raising RuntimeError.

    Used to wait for an experiment's end markers to appear in the
    workload/listener logs. Returns whatever the measure function
    returns once it succeeds.
    """
    deadline = time.time() + timeout
    last_err = None
    while time.time() < deadline:
        try:
            result = measure_fn(*args)
            if on_success is not None:
                on_success(result)
            return result
        except RuntimeError as e:
            last_err = e
            if on_retry is not None:
                on_retry(e)
            time.sleep(sleep)
    raise RuntimeError(f"poll_until timed out after {timeout}s: {last_err}")


def start_listener(server_num, max_server):
    """Spawn listen_and_react.py as a detached subprocess for `server_num`.

    The listener subscribes to the variant's event stream and reacts to
    bundle_updated / bundle_deleted events. Inherits FEDERATION_VARIANT_DIR
    from the parent so its `import repo_client` resolves to the variant's
    transport.
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
    """Highest server number currently present under artefacts/server/, else 0."""
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

    Listener log lines have shape `<epoch> <marker> <trust_domain> <event_epoch>`.
    Returns the most recent epoch where the marker matches `td` and the
    trailing epoch token is >= `since_epoch`. Used by the rotation and
    removal measurement scripts to compute propagation duration.

    Returns None if no fresh match yet (caller polls).
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

    Used by both the event listener (on bundle_updated) and the rotation
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
