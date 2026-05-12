#!/bin/bash

SCRIPT_PATH="$(realpath "$0")"
BASE_DIR="$(echo "$SCRIPT_PATH" | sed -n 's#^\(.*spire-tutorials\).*#\1#p')"

cd centralized-db

CGO_ENABLED=0 GOOS=$(go env GOOS) GOARCH=$(go env GOARCH) go build -v

mv ./centralized-db "$BASE_DIR"/artefacts/bin