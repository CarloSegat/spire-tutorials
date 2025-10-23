#/bin/sh

SCRIPT_PATH="$(realpath "$0")"
DIR="$(dirname $SCRIPT_PATH)"

NUM="$1"
TRUST_DOMAIN_NAME="$2"
FED_PORT="$3"

"$DIR"/bin/spire-server federation create \
    -socketPath /home/carlo/spire-tutorials/host/server/"$NUM"/api.sock \
    -bundleEndpointProfile https_spiffe \
    -trustDomain $TRUST_DOMAIN_NAME \
    -bundleEndpointURL https://localhost:"$FED_PORT" \
    -endpointSpiffeID spiffe://"$TRUST_DOMAIN_NAME"/spire/server

# ./2_create_federation_dynamic.sh 2 broker.example 8082
# ./2_create_federation_dynamic.sh 1 stockmarket.example 8084