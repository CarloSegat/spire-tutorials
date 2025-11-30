#/bin/sh

SCRIPT_PATH="$(realpath "$0")"

DIR="/home/carlo/spire-tutorials/artefacts"

NUM="$1"
TRUST_DOMAIN_NAME="$NUM".snet.example

BUNDLE=$("$DIR"/bin/spire-server bundle show -format spiffe -socketPath "$DIR"/server/"$NUM"/api.sock )

JSON=$(
    printf '{
  "FederationID": "test",
  "QualifiedBundle": {
    "RawBundle": %s,
    "TrustDomainName": "%s"
  }
}' "$(printf '%s\n' "$BUNDLE" | jq -Rs .)" "$TRUST_DOMAIN_NAME")

curl -X POST \
  -H "Content-Type: application/json" \
  -d "$JSON" \
  "http://localhost:8080/bundle"

# ./0_post_bundle.sh 2 stockmarket.example
# ./0_post_bundle.sh 1 broker.example
