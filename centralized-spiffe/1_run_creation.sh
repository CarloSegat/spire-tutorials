#!/bin/sh

if [ $# -lt 1 ]; then
    echo "Error: first argument must be MAX server number" >&2
    exit 1
fi

n=$1

../common/setup_n_clusters.sh $n

sleep 3

exec 3>&1
exec >/dev/null 2>&1

../artefacts/bin/centralized-spiffe &

START_TIME=$(date +%s.%N)
echo "start time=$(date +"%T")" >&3

i=1
while [ $i -le $n ]; do
    echo "Iteration: $i"
    ./post_bundle.sh $i
    i=$((i + 1))
    sleep 0.1
done

sleep 0.1

i=1
while [ $i -le $n ]; do
    ./fetch_bundles.sh $i
    i=$((i + 1))
done

sleep 0.1

cd ../common

i=1
while [ $i -le $n ]; do
    ii=1
    while [ $ii -le $n ]; do
        if [ "$ii" = "$i" ]; then
            ii=$((ii + 1))
            continue
        fi
        echo "Creating federation dynamic for $i $ii"
        ./create_federation_dynamic.sh $i $ii
        # ./3_update_registration_entries.sh $i $ii
        ii=$((ii + 1))
    done
    i=$((i + 1))
done

sleep 1

i=1
while [ $i -le $n ]; do
    ii=1
    while [ $ii -le $n ]; do
        if [ "$ii" = "$i" ]; then
            ii=$((ii + 1))
            continue
        fi
        ./update_registration_entries.sh $i $ii
        ii=$((ii + 1))
    done
    i=$((i + 1))
done

cd ../centralized-spiffe

# Poll until workloads finish
while true; do
    END_RESULT=$(./measure_creation_end.sh $n 2>/dev/null)
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