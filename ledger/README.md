kurtosis clean -a
kurtosis run --enclave local-eth-testnet github.com/ethpandaops/ethereum-package --args-file kurtosis-eth-net.yaml

kurtosis enclave inspect local-eth-testnet

npx hardhat run read.js --network localnet