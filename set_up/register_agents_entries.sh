#!/bin/sh

SERVER_NUM="$1"
DIR="$2"
# AGENT_NUM="$2"
MY_TRUST_DOMAIN_NAME="$SERVER_NUM".snet.example
# THEIR_TRUST_DOMAIN_NAME="$4"

"$DIR"/bin/spire-server entry create \
    -socketPath /home/carlo/spire-tutorials/artefacts/server/"$SERVER_NUM"/api.sock \
	-parentID spiffe://"$MY_TRUST_DOMAIN_NAME"/spire/agent/x509pop/"$MY_TRUST_DOMAIN_NAME"/"$SERVER_NUM"-1 \
	-spiffeID spiffe://"$MY_TRUST_DOMAIN_NAME"/"$SERVER_NUM"-1/workload \
	-selector unix:user:carlo \
	# -federatesWith spiffe://"$THEIR_TRUST_DOMAIN_NAME"

"$DIR"/bin/spire-server entry create \
    -socketPath /home/carlo/spire-tutorials/artefacts/server/"$SERVER_NUM"/api.sock \
	-parentID spiffe://"$MY_TRUST_DOMAIN_NAME"/spire/agent/x509pop/"$MY_TRUST_DOMAIN_NAME"/"$SERVER_NUM"-2 \
	-spiffeID spiffe://"$MY_TRUST_DOMAIN_NAME"/"$SERVER_NUM"-2/workload \
	-selector unix:user:carlo \

