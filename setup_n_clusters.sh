#!/bin/sh

cd ./set_up

./kill_stuff.sh

n=$1

i=1
while [ $i -le $n ]; do
    echo "Iteration: $i"
    ./set_up_cluster.sh $i $n
    i=$((i + 1))
done