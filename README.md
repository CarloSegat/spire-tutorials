# SPIRE Tutorials Fork

## Useful commands

Bundles
`docker compose -f ./docker-compose.yaml exec -T spire-server-broker bin/spire-server bundle show`

`docker compose -f ./docker-compose.yaml exec -T spire-server-broker /opt/spire/bin/spire-server bundle show -format spiffe >`

sh into container without container id
`docker compose -f ./docker-compose.yaml exec -T broker-webapp /bin/sh`

healthcheck of spiffe agents/servers
`docker compose -f ./docker-compose.yaml exec -T broker-webapp bin/spire-agent healthcheck`

Dynamic federation creation
`docker compose -f ./docker-compose.yaml exec -T spire-server-broker /opt/spire/bin/spire-server federation create -bundleEndpointProfile=https_spiffe -trustDomain=stockmarket.example -bundleEndpointURL=https://spire-server-broker:8443 -endpointSpiffeID=spiffe://stockmarket.example/spire/server`

`docker compose -f ./docker-compose.yaml exec -T spire-server-stock /opt/spire/bin/spire-server federation create -bundleEndpointProfile=https_spiffe -trustDomain=broker.example -bundleEndpointURL=https://spire-server-stock:8443 -endpointSpiffeID=spiffe://broker.example/spire/server`
# federates_with "broker.example" {
        #     bundle_endpoint_url = "https://spire-server-broker:8443"
        #     bundle_endpoint_profile "https_spiffe" {
        #         endpoint_spiffe_id = "spiffe://broker.example/spire/server"
        #     }
        # }


./bin/spire-server entry update -entryID c21b0f87-6cd3-48e7-848e-af30885f534f -socketPath /home/carlo/spire-tutorials/host/server/1/api.sock -federatesWith spiffe://2.example.snet -selector unix:user:carlo -parentID spiffe://1.example.snet/spire/agent/x509pop/1.example.snet/1-2
