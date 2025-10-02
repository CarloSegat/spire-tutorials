# SPIRE Tutorials Fork

## Useful commands

Bundles
`docker compose -f ./docker-compose.yaml exec -T spire-server-broker bin/spire-server bundle show` 

`docker compose -f ./docker-compose.yaml exec -T spire-server-broker /opt/spire/bin/spire-server bundle show -format spiffe >`

sh into container without container id
`docker compose -f ./docker-compose.yaml exec -T broker-webapp /bin/sh`

healthcheck of spiffe agents/servers
`docker compose -f ./docker-compose.yaml exec -T broker-webapp bin/spire-agent healthcheck`