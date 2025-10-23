#!/bin/sh
SCRIPT_PATH="$(realpath "$0")"
DIR="$(dirname "$SCRIPT_PATH")"

NUM="$1"
TRUST_DOMAIN_NAME="$2"

BUNDLE=$("$DIR"/bin/spire-server bundle show -format spiffe -socketPath "$DIR"/server/"$NUM"/api.sock)
# printf '%s' "$BUNDLE" > own_bundle.txt
OWN_COMPACT=$(printf '%s' "$BUNDLE" | jq -c .)
# printf '%s' "$OWN_COMPACT" > own_compact.txt
RESPONSE=$(curl -s "http://localhost:8080/bundles/test")
printf '%s' "$RESPONSE" > response_raw.json

cat ./response_raw.json | jq -r '
  .QualifiedBundles[] |
  {name: .TrustDomainName, bundle: (.RawBundle | fromjson)}
' | jq -c '. | [.name, .bundle]' | while read -r line; do
  name=$(echo "$line" | jq -r '.[0]')
  echo "$line" | jq -r '.[1]' > "${name}.json"
done


"$DIR"/bin/spire-server bundle set -id "$TRUST_DOMAIN_NAME" -path ./"$TRUST_DOMAIN_NAME".json -format spiffe -socketPath "$DIR"/server/"$NUM"/api.sock

# ./1_set_bundle.sh 2 broker.example
# ./1_set_bundle.sh 1 stockmarket.example