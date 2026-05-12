#!/bin/bash

set -e

N="${1:-3}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

export PYTHONPATH="$PROJECT_ROOT/common:$PROJECT_ROOT/federation_runtime:$PYTHONPATH"

cd "$SCRIPT_DIR/centralized"

echo "Running centralized SPIFFE sequence with n=$N..."
python3 1_run_creation.py "$N"
python3 2_run_addition.py
python3 3_rotate_key.py 1 "$N"
python3 4_run_removal.py 2 "$N"

echo "Centralized sequence complete"
