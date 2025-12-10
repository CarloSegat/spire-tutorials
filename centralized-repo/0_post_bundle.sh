#!/bin/sh

SCRIPT_PATH="$(cd "$(dirname "$0")" && pwd)"
BASE_DIR="$(echo "$SCRIPT_PATH" | sed -n 's#^\(.*spire-tutorials\).*#\1#p')"
DIR="$BASE_DIR"/artefacts

NUM="$1"
TRUST_DOMAIN_NAME="$NUM".snet.example

# BUNDLE=$("$DIR"/bin/spire-server bundle show -format spiffe -socketPath "$DIR"/server/"$NUM"/api.sock )
BUNDLE=$("$BASE_DIR"/common/print_bundle.sh "$NUM")

echo "BUNDLE $BUNDLE"

FORMATTED_BUNDLE=$(python "$BASE_DIR"/common/format_bundle.py "$TRUST_DOMAIN_NAME" "$BUNDLE") 

python ./post_bundle.py "$FORMATTED_BUNDLE"