#!/usr/bin/env python3
"""Orchestrate removing a server from the federation."""

import os
import subprocess
import sys
import time

import _bootstrap  # noqa: F401  (sys.path side effect)
import spire_utils

import repo_client
import epoch_io
from orchestration import poll_until
from run_self_removal import clean_local_entries
from measure_removal_end import measure_removal_end


def restart_workloads_for_server(removed_num, max_server):
    """Kill and respawn this server's workloads with periodic-send mode enabled.

    The workloads spawned by set_up_cluster.sh go idle after their initial
    mesh handshake, so we can't observe when communication stops. We
    respawn them with PERIODIC_SEND_INTERVAL_SECONDS=1 (1s mTLS probes
    that log periodic_send_success / periodic_send_failed /
    zero_communication_achieved) and SKIP_INITIAL_MESH=1 (skip the
    startup mesh, which would otherwise block forever in talk()'s retry
    loop once peers drop the bundle). Scoped to the removal driver to
    keep other experiments free of periodic-send noise.
    """
    artefacts_dir = spire_utils.artefacts_dir()

    workload_dir = spire_utils.workload_dir(removed_num)
    for i in range(1, 5):
        log_path = workload_dir / str(i) / "workload.log"
        if log_path.exists():
            subprocess.run(
                ["pkill", "-f", f"example-workload.*{workload_dir}/{i}"],
                stderr=subprocess.DEVNULL,
            )

    time.sleep(0.5)

    env = os.environ.copy()
    env["PERIODIC_SEND_INTERVAL_SECONDS"] = "1"
    env["SKIP_INITIAL_MESH"] = "1"
    env["DIR"] = str(artefacts_dir)
    env["NUM"] = str(removed_num)
    env["MAX_NUM"] = str(max_server)
    env["PORT"] = str(9100 + (removed_num * 6 - 5))

    for agent_num in [f"{removed_num}-1", f"{removed_num}-2"]:
        agent_dir = artefacts_dir / "agent" / agent_num
        agent_dir.mkdir(parents=True, exist_ok=True)
        env["SPIFFE_ENDPOINT_SOCKET"] = f"unix://{agent_dir}/api.sock"

        workload_nums = [1, 2] if agent_num.endswith("-1") else [3, 4]
        for w_num in workload_nums:
            w_port = int(env["PORT"]) + 2 + (w_num - 1)
            w_dir = artefacts_dir / "workloads" / str(removed_num) / str(w_num)
            w_dir.mkdir(parents=True, exist_ok=True)
            subprocess.Popen(
                [
                    str(artefacts_dir / "bin" / "example-workload"),
                    str(w_port),
                    str(w_dir),
                    str(removed_num),
                    str(max_server),
                ],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

    print(f"Restarted workloads for server {removed_num} with periodic sends enabled", file=sys.stderr)
    # Workloads sleep 2s on startup then begin periodic sends every 1s.
    # Wait long enough that at least one periodic_send_success is logged before deletion.
    time.sleep(5)


def record_removal_start(removed_num):
    epoch_io.write_epoch(spire_utils.server_dir(removed_num) / "removal_start.epoch")
    print(f"Recorded removal_start.epoch for server {removed_num}", file=sys.stderr)


def _print_removal_result(result):
    print("\nRemoval measurements:", file=sys.stderr)
    print(f"  propagation_duration: {result['propagation']['duration']:.6f}s", file=sys.stderr)
    print(f"  zero_communication_duration: {result['zero_communication']['duration']:.6f}s", file=sys.stderr)


def run_removal(removed_num, server_count):
    """Remove a server from the federation and measure propagation + zero-comm timings."""
    print(f"Removing server {removed_num} from federation ({server_count} total servers)", file=sys.stderr)

    restart_workloads_for_server(removed_num, server_count)
    record_removal_start(removed_num)
    # Single transaction: unilaterally delete the member's bundle from the ledger.
    # No coordination required; deletion is atomic and event-driven propagation
    # to all other federation members is immediate.
    repo_client.delete_bundle(removed_num)
    clean_local_entries(removed_num)

    print("Waiting for removal to propagate and zero-communication to be achieved...", file=sys.stderr)
    poll_until(
        measure_removal_end,
        removed_num,
        server_count,
        sleep=2,
        on_success=_print_removal_result,
        on_retry=lambda e: print(f"  Not ready yet: {e}", file=sys.stderr),
    )


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: run_removal.py <removed_num> <server_count>", file=sys.stderr)
        sys.exit(1)
    run_removal(int(sys.argv[1]), int(sys.argv[2]))
