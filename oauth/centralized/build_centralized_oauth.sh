#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$SCRIPT_DIR/metadata-repo"
CGO_ENABLED=0 go build -v -o oauth-metadata-repo
mkdir -p "$PROJECT_ROOT/artefacts/bin"
cp ./oauth-metadata-repo "$PROJECT_ROOT/artefacts/bin/"

cd "$PROJECT_ROOT/oauth/workload"
CGO_ENABLED=0 go build -v -o oauth-workload
cp ./oauth-workload "$PROJECT_ROOT/artefacts/bin/"

echo "built: oauth-metadata-repo, oauth-workload"
