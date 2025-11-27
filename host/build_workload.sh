#!/bin/bash

SCRIPT_PATH="$(realpath "$0")"
DIR="$(dirname $SCRIPT_PATH)"

cd "$DIR"/../src/example-workload

CGO_ENABLED=0 GOOS=linux go build -v

mv ./example-workload "$DIR"/bin
