#/bin/sh

# delete all data folders or the agents will try to reuse the svids, which will not be valid (because in insecure mode)
find ../artefacts/server/* -delete
find ../artefacts/agent/* -delete
find ../artefacts/workloads/* -delete

pkill spire-server
pkill spire-agent
pkill example-w
pkill centralized-rep