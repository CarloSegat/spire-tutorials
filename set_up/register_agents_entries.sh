#!/bin/sh

SERVER_NUM="$1"
DIR="$2"
MY_TRUST_DOMAIN_NAME="$SERVER_NUM".snet.example

# those entries are for the Agents to give out to the workloads later
# parentID is the agent sort of "owning" the entry


"$DIR"/bin/spire-server entry create \
    -socketPath "$DIR"/server/"$SERVER_NUM"/api.sock \
	-parentID spiffe://"$MY_TRUST_DOMAIN_NAME"/spire/agent/x509pop/"$MY_TRUST_DOMAIN_NAME"/"$SERVER_NUM"-1 \
	-spiffeID spiffe://"$MY_TRUST_DOMAIN_NAME"/"$SERVER_NUM"-1/workload \
	-selector unix:user:"$USER" \


"$DIR"/bin/spire-server entry create \
    -socketPath "$DIR"/server/"$SERVER_NUM"/api.sock \
	-parentID spiffe://"$MY_TRUST_DOMAIN_NAME"/spire/agent/x509pop/"$MY_TRUST_DOMAIN_NAME"/"$SERVER_NUM"-2 \
	-spiffeID spiffe://"$MY_TRUST_DOMAIN_NAME"/"$SERVER_NUM"-2/workload \
	-selector unix:user:"$USER" \

