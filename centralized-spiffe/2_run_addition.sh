#!/bin/sh

SCRIPT_PATH="$(cd "$(dirname "$0")" && pwd)"
BASE_DIR="$(echo "$SCRIPT_PATH" | sed -n 's#^\(.*spire-tutorials\).*#\1#p')"
SERVER_DIR="$BASE_DIR/artefacts/server"

# Find the max server folder number and add 1
max_server=0
for dir in "$SERVER_DIR"/*/; do
    if [ -d "$dir" ]; then
        num=$(basename "$dir")
        if [ "$num" -gt "$max_server" ] 2>/dev/null; then
            max_server=$num
        fi
    fi
done
n=$((max_server + 1))

echo "Adding server $n to the federation"

exec 3>&1
# exec >/dev/null 2>&1

cd ../set_up
./set_up_cluster.sh $n $n
cd ../centralized-spiffe

sleep 3

START_TIME=$(date +%s.%N)
echo "start time=$(date +"%T")" >&3

./post_bundle.sh $n

./fetch_bundles.sh $n

sleep 0.1

cd ../common

ii=1
while [ $ii -le $n ]; do
    if [ "$ii" = "$n" ]; then
        ii=$((ii + 1))
        continue
    fi
    echo "Creating federation dynamic for $n $ii"
    ./create_federation_dynamic.sh $n $ii
    ii=$((ii + 1))
done


sleep 1


ii=1
while [ $ii -le $n ]; do
    if [ "$ii" = "$n" ]; then
        ii=$((ii + 1))
        continue
    fi
    ./update_registration_entries.sh $n $ii
    ii=$((ii + 1))
done

cd ../centralized-spiffe

# Poll until workloads finish
while true; do
    END_RESULT=$(./measure_addition_end.sh $n 2>/dev/null)
    if [ $? -eq 0 ]; then
        break
    fi
    sleep 2
done

END_TIMESTAMP=$(echo "$END_RESULT" | sed -n 's/^end *= *\([0-9-]* [0-9:.]*\).*/\1/p')
END_TIME=$(date -j -f "%Y-%m-%d %H:%M:%S" "${END_TIMESTAMP%.*}" +%s 2>/dev/null || date -d "${END_TIMESTAMP%.*}" +%s)
END_TIME="${END_TIME}.${END_TIMESTAMP##*.}"

DURATION=$(echo "$END_TIME - $START_TIME" | bc)
echo "end time=$END_TIMESTAMP" >&3
echo "duration=${DURATION}s" >&3
