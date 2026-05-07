#!/bin/sh
if [ $# -eq 0 ]; then
    echo "Error: first argument must be server number" >&2
    exit 1
fi

if [ $# -lt 2 ]; then
    echo "Error: second argument must be max server number" >&2
    exit 1
fi

NUM="$1"
MAX_SERVER="$2"

exec 3>&1
exec >/dev/null 2>&1

START_TIME=$(date +%s.%N)
echo "start time=$(date +"%T")" >&3

SCRIPT_PATH="$(cd "$(dirname "$0")" && pwd)"
BASE_DIR="$(echo "$SCRIPT_PATH" | sed -n 's#^\(.*spire-tutorials\).*#\1#p')"
DIR="$BASE_DIR"/artefacts

mkdir -p "$DIR/server/$NUM"
echo "$START_TIME" > "$DIR/server/$NUM/rotation_start.epoch"
rm -f "$DIR/server/$NUM/rotation_end.epoch"

activeAuthorityID=$("$DIR"/bin/spire-server localauthority x509 show -socketPath "$DIR"/server/"$NUM"/api.sock | awk '
/^Active X.509 authority:/ {active=1; next}
/^(Prepared|Old) X.509 authority:/ {active=0}
active && /Authority ID:/ {print $3}
')

preparedAuthorityID=$("$DIR"/bin/spire-server localauthority x509 prepare -socketPath "$DIR"/server/"$NUM"/api.sock | awk -F': ' '/^[[:space:]]*Authority ID:/ {print $2}')

echo "active: $activeAuthorityID, prepared: $preparedAuthorityID" >&3


"$DIR"/bin/spire-server localauthority x509 activate -socketPath "$DIR"/server/"$NUM"/api.sock -authorityID "$preparedAuthorityID"

# can revoke old bundle because is not needed by others to authenticate in order to fetch the new one! They fetch the bundles via the repo
"$DIR"/bin/spire-server localauthority x509 taint -socketPath "$DIR"/server/"$NUM"/api.sock -authorityID "$activeAuthorityID"
# "$DIR"/bin/spire-server localauthority x509 revoke -socketPath "$DIR"/server/"$NUM"/api.sock -authorityID "$activeAuthorityID"

sleep 1

# Update the bundle in the centralized repository because the bundle has changed
TRUST_DOMAIN_NAME="$NUM".snet.example
BUNDLE=$("$BASE_DIR"/common/print_bundle.sh "$NUM")
FORMATTED_BUNDLE=$(python3 "$BASE_DIR"/common/format_bundle.py "$TRUST_DOMAIN_NAME" "$BUNDLE")
python3 "$BASE_DIR"/centralized-spiffe/upsert_bundle.py "$FORMATTED_BUNDLE" >&3

ROTATION_END_EPOCH=$(date +%s.%N)
echo "$ROTATION_END_EPOCH" > "$DIR/server/$NUM/rotation_end.epoch"

echo "Refreshing bundles on all servers except server $NUM using centralized repo" >&3
i=1
while [ $i -le "$MAX_SERVER" ]; do
    if [ "$i" -ne "$NUM" ]; then
        echo "Refreshing bundles from centralized repo for server $i" >&3

        # 1) Fetch bundles from centralized repo
        RESPONSE=$(curl -s "http://localhost:8080/bundles/test")

        # Extract trust domain names from centralized repo response
        REPO_TRUST_DOMAINS=$(echo "$RESPONSE" | python3 -c "
import sys, json
data = json.loads(sys.stdin.read())
for b in data.get('QualifiedBundles', []):
    print(b['TrustDomainName'])
")

        # 2) Get current federations on this server
        CURRENT_FEDERATIONS=$("$DIR"/bin/spire-server federation list -socketPath "$DIR"/server/"$i"/api.sock 2>/dev/null | grep "Trust domain:" | awk '{print $3}')

        # 3) Determine if a member has left (exists in federation but not in repo)
        for fed in $CURRENT_FEDERATIONS; do
            # Skip own trust domain
            if [ "$fed" = "$i.snet.example" ]; then
                continue
            fi

            # Check if this federation exists in the centralized repo
            found=0
            for repo_td in $REPO_TRUST_DOMAINS; do
                if [ "$fed" = "$repo_td" ]; then
                    found=1
                    break
                fi
            done

            if [ "$found" -eq 0 ]; then
                echo "Member $fed has left the federation, removing from server $i" >&3
                "$DIR"/bin/spire-server federation delete -socketPath "$DIR"/server/"$i"/api.sock -id "$fed"
            fi
        done

        # 4) Set bundles from centralized repo (handles key rotations)
        # Write each bundle to a temporary file and set it
        echo "$RESPONSE" | python3 -c "
import sys, json
data = json.loads(sys.stdin.read())
for b in data.get('QualifiedBundles', []):
    td_name = b['TrustDomainName']
    with open(td_name + '.json', 'w') as f:
        f.write(b['RawBundle'])
"

        # Only set the bundle of the server that rotated ($NUM)
        ROTATED_BUNDLE_FILE="$NUM.snet.example.json"
        if [ -f "$ROTATED_BUNDLE_FILE" ]; then
            td_name="${ROTATED_BUNDLE_FILE%.json}"
            echo "Setting bundle for $td_name on server $i" >&3
            "$DIR"/bin/spire-server bundle set -id "$td_name" -path "$ROTATED_BUNDLE_FILE" \
                -format spiffe -socketPath "$DIR"/server/"$i"/api.sock >&3
        fi

        # Clean up all bundle files
        rm -f *.snet.example.json
    fi
    i=$((i + 1))
done

# Poll until workloads finish
while true; do
    END_RESULT=$("$BASE_DIR"/centralized-spiffe/measure_rotation_end.sh 2>/dev/null)
    if [ $? -eq 0 ]; then
        break
    fi
    sleep 0.1
done

echo "$END_RESULT" >&3
