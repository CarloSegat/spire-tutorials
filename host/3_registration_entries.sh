#!/bin/sh

SCRIPT_PATH="$(realpath "$0")"
DIR="$(dirname $SCRIPT_PATH)"

SERVER_NUM="$1"
AGENT_NUM="$2"
MY_TRUST_DOMAIN_NAME="$3"
THEIR_TRUST_DOMAIN_NAME="$4"

"$DIR"/bin/spire-server entry create \
    -socketPath /home/carlo/spire-tutorials/host/server/"$SERVER_NUM"/api.sock \
	-parentID spiffe://"$MY_TRUST_DOMAIN_NAME"/spire/agent/x509pop/"$MY_TRUST_DOMAIN_NAME" \
	-spiffeID spiffe://"$MY_TRUST_DOMAIN_NAME"/"$SERVER_NUM"/"$AGENT_NUM" \
	-selector unix:user:carlo \
	-federatesWith spiffe://"$THEIR_TRUST_DOMAIN_NAME"


