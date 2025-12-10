#!/bin/sh
SCRIPT_PATH="$(cd "$(dirname "$0")" && pwd)"
BASE_DIR="$(echo "$SCRIPT_PATH" | sed -n 's#^\(.*spire-tutorials\).*#\1#p')"
DIR="$BASE_DIR"/artefacts

NUM="$1"

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

find . -name '[0-9]*.snet.example.json' -delete
