#!/bin/bash

SCRIPT_PATH="$(realpath "$0")"
DIR="$(dirname $SCRIPT_PATH)"

cd ./src/example-workload

CGO_ENABLED=0 GOOS=$(go env GOOS) GOARCH=$(go env GOARCH) go build -v


mv ./example-workload ../../artefacts/bin
