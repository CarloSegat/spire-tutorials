#!/bin/sh

n=$1

./artefacts/bin/centralized-repo &

cd ./centralized-repo

echo "time=$(date +"%T")"

i=1
while [ $i -le $n ]; do
    echo "Iteration: $i"
    ./0_post_bundle.sh $i
    i=$((i + 1))
    sleep 0.1
done

sleep 0.1

i=1
while [ $i -le $n ]; do
    ii=1
    while [ $ii -le $n ]; do
        if [ "$ii" = "$i" ]; then
            ii=$((ii + 1))
            continue
        fi
        ./1_fetch_bundles.sh $i $ii
        ii=$((ii + 1))
    done
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