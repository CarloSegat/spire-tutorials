#!/bin/bash

SCRIPT_PATH="$(realpath "$0")"
DIR="$(dirname $SCRIPT_PATH)"

cd "$DIR"/../src/broker-webapp

CGO_ENABLED=0 GOOS=linux go build -v

mv ./broker-webapp "$DIR"/bin
