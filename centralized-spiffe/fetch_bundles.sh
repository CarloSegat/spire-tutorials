#!/bin/sh
SCRIPT_PATH="$(cd "$(dirname "$0")" && pwd)"
BASE_DIR="$(echo "$SCRIPT_PATH" | sed -n 's#^\(.*spire-tutorials\).*#\1#p')"
DIR="$BASE_DIR"/artefacts

NUM="$1"
# TRUST_DOMAIN_NAME="$2"

BUNDLE=$("$DIR"/bin/spire-server bundle show -format spiffe -socketPath "$DIR"/server/"$NUM"/api.sock)
# printf '%s' "$BUNDLE" > own_bundle.txt
OWN_COMPACT=$(printf '%s' "$BUNDLE" | jq -c .)
# printf '%s' "$OWN_COMPACT" > own_compact.txt
RESPONSE=$(curl -s "http://localhost:8080/bundles/test")
printf '%s' "$RESPONSE" > response_raw.json

python3 ./split_raw_response.py

rm response_raw.json

"$BASE_DIR"/common/set_bundle.sh "$NUM"
