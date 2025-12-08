#!/bin/bash

SCRIPT_PATH="$(realpath "$0")"
DIR="$(dirname $SCRIPT_PATH)"

cd ./src/centralized-repo

CGO_ENABLED=0 GOOS=$(go env GOOS) GOARCH=$(go env GOARCH) go build -v

mv ./centralized-repo "$DIR"/artefacts/bin