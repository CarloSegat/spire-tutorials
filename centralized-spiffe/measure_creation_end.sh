#!/bin/sh

if [ $# -lt 1 ]; then
    echo "Error: first argument must be number of servers created (n)" >&2
    exit 1
fi

n=$1

SCRIPT_PATH="$(cd "$(dirname "$0")" && pwd)"
BASE_DIR="$(echo "$SCRIPT_PATH" | sed -n 's#^\(.*spire-tutorials\).*#\1#p')"
DIR="$BASE_DIR"/artefacts

WORKLOADS_DIR="$DIR"/workloads

if [ ! -d "$WORKLOADS_DIR" ]; then
    echo "Error: workloads directory not found: $WORKLOADS_DIR" >&2
    exit 1
fi

START_MARKER="Experiment begins"
END_MARKER="All messages sent, experiemnt is finished"

MATCH_COUNT=0
LOWEST_START=""
HIGHEST_END=""
HIGHEST_END_FILE=""

i=1
while [ $i -le $n ]; do
    SERVER_DIR="$WORKLOADS_DIR/$i"
    if [ ! -d "$SERVER_DIR" ]; then
        echo "Error: server directory not found: $SERVER_DIR" >&2
        exit 1
    fi

    for log_file in "$SERVER_DIR"/*/workload.log; do
        if [ ! -f "$log_file" ]; then
            continue
        fi

        while IFS= read -r line; do
            TIMESTAMP=$(echo "$line" | sed -n 's/.*time="\([^"]*\)".*/\1/p')
            [ -z "$TIMESTAMP" ] && continue

            if echo "$line" | grep -q "$START_MARKER"; then
                if [ -z "$LOWEST_START" ] || [ "$TIMESTAMP" \< "$LOWEST_START" ]; then
                    LOWEST_START="$TIMESTAMP"
                fi
            fi

            if echo "$line" | grep -q "$END_MARKER"; then
                MATCH_COUNT=$((MATCH_COUNT + 1))
                if [ -z "$HIGHEST_END" ] || [ "$TIMESTAMP" \> "$HIGHEST_END" ]; then
                    HIGHEST_END="$TIMESTAMP"
                    HIGHEST_END_FILE="$log_file"
                fi
            fi
        done < "$log_file"
    done
    i=$((i + 1))
done

EXPECTED=$((n * 4))
if [ "$MATCH_COUNT" -ne "$EXPECTED" ]; then
    echo "❌ FAIL: end-marker occurrences ($MATCH_COUNT) != expected ($EXPECTED = $n servers * 4 workloads)" >&2
    exit 1
fi

if [ -z "$LOWEST_START" ] || [ -z "$HIGHEST_END" ]; then
    echo "⚠ WARNING: missing start or end timestamp" >&2
    exit 1
fi

to_epoch() {
    ts="$1"
    base="${ts%.*}"
    ms="${ts##*.}"
    epoch=$(date -j -f "%Y-%m-%d %H:%M:%S" "$base" +%s 2>/dev/null) \
        || epoch=$(date -d "$base" +%s)
    echo "${epoch}.${ms}"
}

START_EPOCH=$(to_epoch "$LOWEST_START")
END_EPOCH=$(to_epoch "$HIGHEST_END")
DURATION=$(echo "$END_EPOCH - $START_EPOCH" | bc)

echo "start    = $LOWEST_START"
echo "end      = $HIGHEST_END  ($HIGHEST_END_FILE)"
echo "duration = ${DURATION}s"
