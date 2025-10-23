#!/bin/sh


pkill  spire-server
pkill  spire-agent

SCRIPT_PATH="$(realpath "$0")"
DIR="$(dirname $SCRIPT_PATH)"

# delete all data folders or the agents will try to reuse the svids, which will not be valid (because in insecure mode)
find "$DIR" -type d -name "data" -exec rm -rf {} +

export NUM=1
export PORT=8081
export FED_PORT=8082
export DOMAIN="broker.example"
"$DIR"/bin/spire-server run -expandEnv -config "$DIR"/server/"$NUM"/server.conf &
export NUM=1-1
"$DIR"/bin/spire-agent run -expandEnv -config "$DIR"/agent/"$NUM"/agent.conf  &

export NUM=2
export PORT=8083
export FED_PORT=8084
export DOMAIN="stockmarket.example"
"$DIR"/bin/spire-server run -expandEnv -config "$DIR"/server/"$NUM"/server.conf &
export NUM=2-1
"$DIR"/bin/spire-agent run -expandEnv -config "$DIR"/agent/"$NUM"/agent.conf  &