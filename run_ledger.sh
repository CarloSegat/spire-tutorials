#!/bin/sh

if [ $# -eq 0 ]; then
    echo "Error: first argument must be server count" >&2
    exit 1
fi

SCRIPT_PATH="$(cd "$(dirname "$0")" && pwd)"
BASE_DIR="$(echo "$SCRIPT_PATH" | sed -n 's#^\(.*spire-tutorials\).*#\1#p')"

n=$1

kurtosis clean -a

python ./ledger/kurtosis-configs/build_kurtosis_config.py $n

kurtosis run --enclave local-eth-testnet github.com/ethpandaops/ethereum-package --args-file ./ledger/kurtosis-configs/kurtosis-eth-net.yaml

HARDHAT_VAR_KURTOSIS_RPC="$(kurtosis port print local-eth-testnet el-1-geth-lighthouse rpc)"
echo $HARDHAT_VAR_KURTOSIS_RPC

sleep 45.0

cd ledger/harhat-project/

CONTRACT_ADDRESS=$(npx hardhat deploy --rpc http://"$HARDHAT_VAR_KURTOSIS_RPC" --index 1) 

# remove empty lines
CONTRACT_ADDRESS=$(echo "$CONTRACT_ADDRESS" | awk '/^[ \t]*$/ {next;} {print}')

echo "CONTRACT_ADDRESS >> $CONTRACT_ADDRESS"

i=1
while [ $i -le $n ]; do
    echo "Iteration: $i"

    HARDHAT_VAR_KURTOSIS_RPC="$(kurtosis port print local-eth-testnet el-"$i"-geth-lighthouse rpc)"
    BUNDLE=$("$BASE_DIR"/common/print_bundle.sh "$i")

    # write through a different node to simulate real scenario
    npx hardhat write_bundle \
        --rpc http://"$HARDHAT_VAR_KURTOSIS_RPC" \
        --index "$i" \
        --bundle "$BUNDLE" \
        --contract "$CONTRACT_ADDRESS"

    sleep 0.5

    i=$((i + 1))
done

i=1
while [ $i -le $n ]; do
    echo "Iteration: $i"

    HARDHAT_VAR_KURTOSIS_RPC="$(kurtosis port print local-eth-testnet el-"$i"-geth-lighthouse rpc)"

    BUNDLES=$(npx hardhat read_bundles \
        --rpc http://"$HARDHAT_VAR_KURTOSIS_RPC" \
        --index "$i" \
        --contract "$CONTRACT_ADDRESS" | awk '/^[ \t]*$/ {next;} {print}')

    echo "BUNDLES >>> $BUNDLES"

    # cd ..

    python ../split_bundles.py "$BUNDLES"

    "$BASE_DIR"/common/set_bundle.sh "$i"

    # cd harhat-project/

    i=$((i + 1))
done

cd "$BASE_DIR"/common

sleep 2

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

sleep 2

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