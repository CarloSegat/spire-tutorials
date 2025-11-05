#!/bin/sh
SCRIPT_PATH="$(realpath "$0")"
DIR="$(dirname "$SCRIPT_PATH")"

NUM="$1"
# TRUST_DOMAIN_NAME="$2"

BUNDLE=$("$DIR"/bin/spire-server bundle show -format spiffe -socketPath "$DIR"/server/"$NUM"/api.sock)
# printf '%s' "$BUNDLE" > own_bundle.txt
OWN_COMPACT=$(printf '%s' "$BUNDLE" | jq -c .)
# printf '%s' "$OWN_COMPACT" > own_compact.txt
RESPONSE=$(curl -s "http://localhost:8080/bundles/test")
printf '%s' "$RESPONSE" > response_raw.json

python3 ./split_raw_response.py


rm response_raw.json


matching_files=$(ls [0-9].snet.example.json [0-9][0-9].snet.example.json 2>/dev/null)
if [ -n "$matching_files" ]; then
    set -- $matching_files  # Temporarily set positional params to the file list
    while [ $# -gt 0 ]; do
        file="$1"
        if [ -f "$file" ]; then  # Redundant here but keeps your original logic
            num="${file%%.*}"
            echo "Number: $num, File: $file"
	    if [ "$num" = "$NUM" ]; then
                echo "Skipping own file: $file (num=$num matches NUM=$NUM)"
                shift
                continue
            fi
	    "$DIR"/bin/spire-server bundle set -id "$num".snet.example -path "$num".snet.example.json \
		-format spiffe -socketPath "$DIR"/server/"$NUM"/api.sock

        fi
        shift  # Move to next file
    done
else
    echo "No matching files found (pattern: [0-9][0-9].snet.example.json)"
fi

find . -name '[0-9]*.snet.json' -delete

# ./1_set_bundle.sh 2 broker.example
# ./1_set_bundle.sh 1 stockmarket.example
