#!/usr/bin/env bash
set -e

N="${1:-3}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

export PYTHONPATH="$SCRIPT_DIR/ledger:$SCRIPT_DIR:$PYTHONPATH"

cd "$SCRIPT_DIR/ledger"

echo "[cleanup] killing stale processes and state"
pkill -f 'quarkus|kc.sh|keycloak' 2>/dev/null || true
pkill -f 'hardhat node' 2>/dev/null || true
pkill -f oauth-workload 2>/dev/null || true
pkill -f listen_and_react.py 2>/dev/null || true
# Kill anything bound to KC ports (8081-8099), workload ports, and Hardhat
PIDS=$(lsof -ti:8081,8082,8083,8084,8085,8086,8087,8088,8089,8090,8545 2>/dev/null || true)
if [ -n "$PIDS" ]; then
  echo "$PIDS" | xargs kill -9 2>/dev/null || true
fi
WPIDS=$(lsof -ti:7010,7011,7012,7013,7020,7021,7022,7023,7030,7031,7032,7033,7040,7041,7042,7043,7050,7051,7052,7053 2>/dev/null || true)
if [ -n "$WPIDS" ]; then
  echo "$WPIDS" | xargs kill -9 2>/dev/null || true
fi
rm -rf "$SCRIPT_DIR/ledger/pids" "$SCRIPT_DIR/ledger/logs" "$SCRIPT_DIR/ledger/epochs" "$PROJECT_ROOT/artefacts/keycloak-data"
sleep 1

echo "Running ledger OAuth sequence with n=$N..."
python3 1_run_creation.py "$N"
python3 2_run_addition.py
python3 3_rotate_key.py
python3 4_run_removal.py

echo "Ledger OAuth sequence complete"
