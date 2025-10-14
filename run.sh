#!/bin/sh

docker compose down

DOCKER_BUILDKIT=0 ./build.sh

docker compose up -d