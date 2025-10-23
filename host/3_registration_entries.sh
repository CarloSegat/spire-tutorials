#!/bin/sh

SCRIPT_PATH="$(realpath "$0")"
DIR="$(dirname $SCRIPT_PATH)"

"$DIR"/bin/spire-server entry create \
    -socketPath /home/carlo/spire-tutorials/host/server/api.sock \
	-parentID spiffe://broker.example/spire/agent/x509pop/broker.example \
	-spiffeID spiffe://broker.example/webapp \
	-selector unix:user:carlo \
	-federatesWith "spiffe://stockmarket.example"