#!/usr/bin/env python3
import sys
import os
import csv

def read_epoch(name):
    path = f"ledger/epochs/{name}.epoch"
    try:
        return float(open(path).read().strip())
    except FileNotFoundError:
        print(f"ERROR: {path} not found. Did you run run_ledger.sh?", file=sys.stderr)
        sys.exit(1)
    except ValueError:
        print(f"ERROR: Invalid epoch value in {path}", file=sys.stderr)
        sys.exit(1)

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 measure_ledger.py <N>", file=sys.stderr)
        sys.exit(1)

    try:
        n = int(sys.argv[1])
    except ValueError:
        print(f"ERROR: N must be an integer, got '{sys.argv[1]}'", file=sys.stderr)
        sys.exit(1)

    if not os.path.isdir("ledger/epochs"):
        print("ERROR: ledger/epochs/ directory not found. Run from oauth/ directory.", file=sys.stderr)
        sys.exit(1)

    t_creation_start = read_epoch("creation_start")
    t_creation_stop = read_epoch("creation_stop")
    t_addition_start = read_epoch("addition_start")
    t_addition_stop = read_epoch("addition_stop")
    t_rotation_start = read_epoch("rotation_start")
    t_rotation_stop = read_epoch("rotation_stop")
    t_propagation_stop = read_epoch("propagation_stop")
    t_mesh_stop = read_epoch("post_rotation_mesh_stop")
    t_removal_start = read_epoch("removal_start")
    t_removal_stop = read_epoch("removal_stop")

    creation_s = t_creation_stop - t_creation_start
    addition_s = t_addition_stop - t_addition_start
    rotation_call_s = t_rotation_stop - t_rotation_start
    propagation_s = t_propagation_stop - t_rotation_stop
    mesh_after_rotation_s = t_mesh_stop - t_propagation_stop
    removal_s = t_removal_stop - t_removal_start

    row = ["ledger", n, creation_s, addition_s, rotation_call_s, propagation_s, mesh_after_rotation_s, removal_s]

    csv_path = "results.csv"
    file_exists = os.path.isfile(csv_path)

    with open(csv_path, "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["variant", "n", "creation_s", "addition_s", "rotation_call_s", "propagation_s", "mesh_after_rotation_s", "removal_s"])
        writer.writerow(row)

    print(f"variant=ledger N={n}")
    print(f"  creation: {creation_s:.3f}s")
    print(f"  addition: {addition_s:.3f}s")
    print(f"  rotation_call: {rotation_call_s:.3f}s")
    print(f"  propagation: {propagation_s:.3f}s")
    print(f"  mesh_after_rotation: {mesh_after_rotation_s:.3f}s")
    print(f"  removal: {removal_s:.3f}s")
    print(f"\nAppended to {csv_path}")

if __name__ == "__main__":
    main()
