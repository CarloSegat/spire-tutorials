#!/bin/sh

if [ $# -lt 2 ]; then
    echo "Error: first argument must be server number, second argument must be max server number" >&2
    exit 1
fi

MY_NUM=$1
MAX_SERVER=$2

SCRIPT_PATH="$(cd "$(dirname "$0")" && pwd)"
BASE_DIR="$(echo "$SCRIPT_PATH" | sed -n 's#^\(.*spire-tutorials\).*#\1#p')"
DIR="$BASE_DIR"/artefacts

TRUST_DOMAIN_NAME="$MY_NUM".snet.example
FEDERATION_ID="test"

# Delete the bundle from the centralized repository
echo "Deleting bundle for TrustDomainName $TRUST_DOMAIN_NAME from FederationID $FEDERATION_ID"
DELETE_RESPONSE=$(curl -s -X DELETE "http://localhost:8080/bundle" \
    -H "Content-Type: application/json" \
    -d "{\"FederationID\": \"$FEDERATION_ID\", \"TrustDomainName\": \"$TRUST_DOMAIN_NAME\"}")

echo "Delete response: $DELETE_RESPONSE"

# Update registration entries to remove federation trust from all other domains
# By not including -federatesWith flags, we remove trust relationships
"$DIR"/bin/spire-server entry show -socketPath "$DIR"/server/"$MY_NUM"/api.sock | awk -F': ' '/Entry/ {printf $2} /SPIFFE/ {printf " %s", $2}  /Parent/ {printf " %s\n", $2;}' |
while IFS= read -r line
do
    echo "Processing entry removal: $line"
    ENTRY_ID=$(echo $line | awk -F' ' '{print $1}')
    SPIFFE_ID=$(echo $line | awk -F' ' '{print $2}')
    PARENT_ID=$(echo $line | awk -F' ' '{print $3}')

    echo "Removing federation trust from entry $ENTRY_ID (SPIFFE_ID: $SPIFFE_ID)"

    # Update entry without -federatesWith flags to remove all federation trust
    "$DIR"/bin/spire-server entry update \
        -entryID "$ENTRY_ID" \
        -socketPath "$DIR"/server/"$MY_NUM"/api.sock \
        -selector unix:user:"$USER" \
        -parentID "$PARENT_ID" \
        -spiffeID "$SPIFFE_ID"
        # Note: No -federatesWith flags means no federation trust
done

echo "Removed federation trust from all registration entries on server $MY_NUM"
