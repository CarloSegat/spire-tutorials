#/bin/sh

SCRIPT_PATH="$(cd "$(dirname "$0")" && pwd)"
BASE_DIR="$(echo "$SCRIPT_PATH" | sed -n 's#^\(.*spire-tutorials\).*#\1#p')"
DIR="$BASE_DIR"/artefacts

NUM="$1"
OTHER_NUM="$2"
FED_PORT=$(( 8083 + ($OTHER_NUM * 6 - 4)))
TRUST_DOMAIN_NAME="$OTHER_NUM".snet.example

"$DIR"/bin/spire-server federation create \
    -socketPath "$DIR"/server/"$NUM"/api.sock \
    -bundleEndpointProfile https_spiffe \
    -trustDomain $TRUST_DOMAIN_NAME \
    -bundleEndpointURL https://localhost:"$FED_PORT" \
    -endpointSpiffeID spiffe://"$TRUST_DOMAIN_NAME"/spire/server