#!/bin/bash

N="${1:-3}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

export PYTHONPATH="$PROJECT_ROOT/common:$PROJECT_ROOT/federation_runtime:$PYTHONPATH"

cd "$PROJECT_ROOT/federation_runtime"

echo "=========================================="
echo "LEDGER MEASUREMENT RESULTS"
echo "=========================================="
echo ""

echo "Creation:"
python3 measure_creation_end.py "$N" 2>/dev/null || echo "FAILED"
echo ""

echo "Addition:"
python3 measure_addition_end.py "$N" 2>/dev/null || echo "FAILED"
echo ""

echo "Rotation (server 1, n=$N):"
python3 measure_rotation_end.py 1 "$N" 2>/dev/null || echo "FAILED"
echo ""

echo "Removal (server 2, n=$N):"
python3 measure_removal_end.py 2 "$N" 2>/dev/null || echo "FAILED"
