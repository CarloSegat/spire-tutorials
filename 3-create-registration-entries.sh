#/bin/bash

set -e

bb=$(tput bold)
nn=$(tput sgr0)

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"


echo "${bb}Creating registration entry for the broker-webapp...${nn}"
docker compose -f "${DIR}"/docker-compose.yaml exec -T spire-server-broker bin/spire-server entry create \
	-parentID spiffe://broker.example/spire/agent/x509pop/broker.example \
	-spiffeID spiffe://broker.example/webapp \
	-selector unix:user:carlo \
	-federatesWith "spiffe://stockmarket.example"

echo "${bb}Creating registration entry for the stock-quotes-service...${nn}"
docker compose -f "${DIR}"/docker-compose.yaml exec -T spire-server-stock bin/spire-server entry create \
	-parentID spiffe://stockmarket.example/spire/agent/x509pop/stockmarket.example \
	-spiffeID spiffe://stockmarket.example/quotes-service \
	-selector unix:uid:0 \
	-federatesWith "spiffe://broker.example"
