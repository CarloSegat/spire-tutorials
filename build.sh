#!/bin/bash

set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# build server
(cd "${DIR}"/src/common-server && CGO_ENABLED=0 GOOS=linux go build -v -o "${DIR}"/docker/spire-server-broker.example/common-server)
(cd "${DIR}"/src/common-server && CGO_ENABLED=0 GOOS=linux go build -v -o "${DIR}"/docker/spire-server-stockmarket.example/common-server)

# build the agents/workloads
(cd "${DIR}"/src/broker-webapp && CGO_ENABLED=0 GOOS=linux go build -v -o "${DIR}"/docker/broker-webapp/broker-webapp)
(cd "${DIR}"/src/stock-quotes-service && CGO_ENABLED=0 GOOS=linux go build -v -o "${DIR}"/docker/stock-quotes-service/stock-quotes-service)

docker compose -f "${DIR}"/docker-compose.yaml build
