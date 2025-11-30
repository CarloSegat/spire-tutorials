#!/bin/sh

./kill_stuff.sh
./artefacts/bin/centralized-repo &
n=$1
cd set_up
i=1
while [ $i -le $n ]; do
    echo "Iteration: $i"
    ./set_up_cluster.sh $i $n
    i=$((i + 1))
done

sleep 5
cd ../centralized-repo

i=1
while [ $i -le $n ]; do
    echo "Iteration: $i"
    ./0_post_bundle.sh $i
    i=$((i + 1))
done

sleep 5

i=1
while [ $i -le $n ]; do
    ii=1
    while [ $ii -le $n ]; do
        if [ "$ii" = "$i" ]; then
            ii=$((ii + 1))
            continue
        fi
        ./1_set_bundle.sh $i $ii
        ii=$((ii + 1))
    done
    i=$((i + 1))
done
sleep 5
i=1
while [ $i -le $n ]; do
    ii=1
    while [ $ii -le $n ]; do
        if [ "$ii" = "$i" ]; then
            ii=$((ii + 1))
            continue
        fi
        ./2_create_federation_dynamic.sh $i $ii
        ./3_update_registration_entries.sh $i $ii
        ii=$((ii + 1))
    done
    i=$((i + 1))
done
# cd ../centralized-repo
# ./0_post_bundle.sh 1
# ./0_post_bundle.sh 2
# ./1_set_bundle.sh 1 2
# ./1_set_bundle.sh 2 1
# ./2_create_federation_dynamic.sh 1 2
# ./2_create_federation_dynamic.sh 2 1
# ./3_update_registration_entries.sh 1 2
# ./3_update_registration_entries.sh 2 1