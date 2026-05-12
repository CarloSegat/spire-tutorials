#!/usr/bin/env python3
"""Aggregate SPIFFE/ledger measurement results into CSV format.

Collects all 6 metrics from the 4 measurement scripts and outputs as a CSV row.
Appends to results.csv for accumulation across multiple federation sizes.
"""
import sys
import os
import csv

# Add federation_runtime to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'federation_runtime'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'common'))

from measure_creation_end import measure_creation_end
from measure_addition_end import measure_addition_end
from measure_rotation_end import measure_rotation_end
from measure_removal_end import measure_removal_end


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 measure_ledger.py <N>", file=sys.stderr)
        sys.exit(1)

    try:
        n = int(sys.argv[1])
    except ValueError:
        print(f"ERROR: N must be an integer, got '{sys.argv[1]}'", file=sys.stderr)
        sys.exit(1)

    # Change to federation_runtime for relative path resolution
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    fed_runtime_dir = os.path.join(project_root, 'federation_runtime')
    os.chdir(fed_runtime_dir)

    try:
        # Suppress stdout from measure functions during collection
        from io import StringIO
        old_stdout = sys.stdout

        # Measure creation
        sys.stdout = StringIO()
        _, _, creation_s = measure_creation_end(n)
        sys.stdout = old_stdout

        # Measure addition
        sys.stdout = StringIO()
        _, _, addition_s = measure_addition_end(n)
        sys.stdout = old_stdout

        # Measure rotation (server 1 is rotated)
        sys.stdout = StringIO()
        rotation_results = measure_rotation_end(rotated_num=1, server_count=n)
        sys.stdout = old_stdout
        rotation_call_s = rotation_results["rotation"]["duration"]
        propagation_s = rotation_results["propagation"]["duration"]
        mesh_after_rotation_s = rotation_results["full_mesh"]["duration"]

        # Measure removal (server 2 is removed)
        sys.stdout = StringIO()
        removal_results = measure_removal_end(removed_num=2, server_count=n)
        sys.stdout = old_stdout
        removal_s = removal_results["propagation"]["duration"]
        zero_communication_s = removal_results["zero_communication"]["duration"]

    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        sys.stdout = old_stdout

    # Prepare row
    row = [n, creation_s, addition_s, rotation_call_s, propagation_s, mesh_after_rotation_s, removal_s, zero_communication_s]

    # Write to results.csv (relative to spiffe dir)
    csv_path = os.path.join(script_dir, 'results.csv')
    file_exists = os.path.isfile(csv_path)

    with open(csv_path, 'a', newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(['n', 'creation_s', 'addition_s', 'rotation_call_s', 'propagation_s', 'mesh_after_rotation_s', 'removal_s', 'zero_communication_s'])
        writer.writerow(row)

    # Print to stdout in human-readable form
    print(f"N={n}")
    print(f"  creation: {creation_s:.3f}s")
    print(f"  addition: {addition_s:.3f}s")
    print(f"  rotation_call: {rotation_call_s:.3f}s")
    print(f"  propagation: {propagation_s:.3f}s")
    print(f"  mesh_after_rotation: {mesh_after_rotation_s:.3f}s")
    print(f"  removal: {removal_s:.3f}s")
    print(f"  zero_communication: {zero_communication_s:.3f}s")
    print(f"\nAppended to {csv_path}")


if __name__ == "__main__":
    main()
