#/bin/bash

set -e

bb=$(tput bold)
nn=$(tput sgr0)

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "${bb}using federation create to set up the federation dynamically wihtout hardcode it in the configs${nn}"

docker compose -f "${DIR}"/docker-compose.yaml exec -T spire-server-broker /opt/spire/bin/spire-server federation create -bundleEndpointProfile=https_spiffe -trustDomain=stockmarket.example -bundleEndpointURL=https://spire-server-broker:8443 -endpointSpiffeID=spiffe://stockmarket.example/spire/server

docker compose -f "${DIR}"/docker-compose.yaml exec -T spire-server-stock /opt/spire/bin/spire-server federation create -bundleEndpointProfile=https_spiffe -trustDomain=broker.example -bundleEndpointURL=https://spire-server-stock:8443 -endpointSpiffeID=spiffe://broker.example/spire/server