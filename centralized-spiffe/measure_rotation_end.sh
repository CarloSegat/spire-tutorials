#!/bin/sh

SCRIPT_PATH="$(cd "$(dirname "$0")" && pwd)"
BASE_DIR="$(echo "$SCRIPT_PATH" | sed -n 's#^\(.*spire-tutorials\).*#\1#p')"
DIR="$BASE_DIR"/artefacts

WORKLOADS_DIR="$DIR"/workloads

if [ ! -d "$WORKLOADS_DIR" ]; then
    echo "Error: workloads directory not found: $WORKLOADS_DIR" >&2
    exit 1
fi

# Auto-detect rotated server from logs.
# Pick the server number from the most recent "updated for server X" log entry.
ROTATED_NUM=$(grep -h "Federation bundle certificate serials updated for server" \
    "$WORKLOADS_DIR"/*/*/workload.log 2>/dev/null \
    | sort -t'"' -k2 \
    | tail -1 \
    | sed -n 's/.*updated for server \([0-9]*\).*/\1/p')

if [ -z "$ROTATED_NUM" ]; then
    echo "Error: could not auto-detect rotated server (no rotation log entries found)" >&2
    exit 1
fi

# Count server folders (top-level directories in workloads/)
SERVER_COUNT=0
for server_dir in "$WORKLOADS_DIR"/*/; do
    if [ -d "$server_dir" ]; then
        SERVER_COUNT=$((SERVER_COUNT + 1))
    fi
done

START_MARKER="Starting special communication: communicating again after key rotation"
END_MARKER="Finished special communication: communicating again after key rotation"

MATCH_COUNT=0
LOWEST_START=""
HIGHEST_END=""
HIGHEST_END_FILE=""

for log_file in "$WORKLOADS_DIR"/*/*/workload.log; do
    if [ ! -f "$log_file" ]; then
        continue
    fi

    # Skip the rotated server's own logs (they don't emit rotation messages)
    server_dir=$(basename "$(dirname "$(dirname "$log_file")")")
    if [ "$server_dir" = "$ROTATED_NUM" ]; then
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

EXPECTED=$(((SERVER_COUNT - 1) * 4))
if [ "$MATCH_COUNT" -ne "$EXPECTED" ]; then
    echo "FAIL: end-marker occurrences ($MATCH_COUNT) != expected ($EXPECTED = (SERVER_COUNT-1) * 4 workloads)" >&2
    exit 1
fi

if [ -z "$LOWEST_START" ] || [ -z "$HIGHEST_END" ]; then
    echo "WARNING: missing start or end timestamp" >&2
    exit 1
fi

to_epoch() {
    ts="$1"
    base="${ts%.*}"
    if [ "$base" = "$ts" ]; then
        ms="0"
    else
        ms="${ts##*.}"
    fi
    epoch=$(date -j -f "%Y-%m-%d %H:%M:%S" "$base" +%s 2>/dev/null) \
        || epoch=$(date -d "$base" +%s)
    echo "${epoch}.${ms}"
}

epoch_to_human() {
    e="$1"
    secs="${e%.*}"
    if [ "$secs" = "$e" ]; then
        ms="000"
    else
        ms="${e##*.}"
        ms=$(echo "$ms" | cut -c1-3)
    fi
    base=$(date -r "$secs" "+%Y-%m-%d %H:%M:%S" 2>/dev/null) \
        || base=$(date -d "@$secs" "+%Y-%m-%d %H:%M:%S")
    echo "${base}.${ms}"
}

# Rotation block (read marker files written by 3_rotate_key.sh)
ROTATION_START_FILE="$DIR/server/$ROTATED_NUM/rotation_start.epoch"
ROTATION_END_FILE="$DIR/server/$ROTATED_NUM/rotation_end.epoch"

if [ -f "$ROTATION_START_FILE" ] && [ -f "$ROTATION_END_FILE" ]; then
    ROTATION_START_EPOCH=$(cat "$ROTATION_START_FILE")
    ROTATION_END_EPOCH=$(cat "$ROTATION_END_FILE")
    ROTATION_DURATION=$(echo "$ROTATION_END_EPOCH - $ROTATION_START_EPOCH" | bc)
    ROTATION_START_HUMAN=$(epoch_to_human "$ROTATION_START_EPOCH")
    ROTATION_END_HUMAN=$(epoch_to_human "$ROTATION_END_EPOCH")
    echo "rotation_start         = $ROTATION_START_HUMAN"
    echo "rotation_end           = $ROTATION_END_HUMAN"
    echo "rotation_duration      = ${ROTATION_DURATION}s"
fi

# Communication block
COMM_START_EPOCH=$(to_epoch "$LOWEST_START")
COMM_END_EPOCH=$(to_epoch "$HIGHEST_END")
COMM_DURATION=$(echo "$COMM_END_EPOCH - $COMM_START_EPOCH" | bc)

echo "communication_start    = $LOWEST_START"
echo "communication_end      = $HIGHEST_END  ($HIGHEST_END_FILE)"
echo "communication_duration = ${COMM_DURATION}s"
