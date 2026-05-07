# Plan: ledger-spiffe

## Context
Mirror `centralized-repo/` into `ledger-spiffe/`, replacing the Go HTTP bundle server with a Solidity smart contract on a local Hardhat node. Bundle writes = on-chain transactions; reads = `eth_call` to Hardhat RPC (`http://localhost:8545`). Python scripts use `web3.py`. `updateBundle()` explicitly deletes old storage (SSTORE gas refund) then writes new bundle — enables gas cost measurement on Hardhat.

---

## What Moves to common/
Scripts identical between centralized-repo and ledger-spiffe go to `common/` (referenced by both):
- `measure_creation_end.sh` ← move from centralized-repo/
- `measure_addition_end.sh` ← move from centralized-repo/
- `measure_rotation_end.sh` ← move from centralized-repo/
- `split_raw_response.py` ← move from centralized-repo/

---

## Directory Layout

```
common/                          ← existing + newly moved scripts
  create_federation_dynamic.sh   (existing)
  format_bundle.py               (existing)
  set_bundle.sh                  (existing)
  setup_n_clusters.sh            (existing)
  update_registration_entries.sh (existing)
  measure_creation_end.sh        ← moved here
  measure_addition_end.sh        ← moved here
  measure_rotation_end.sh        ← moved here
  split_raw_response.py          ← moved here

centralized-repo/                ← update paths to reference common/
  1_run_creation.sh
  2_run_addition.sh
  3_rotate_key.sh
  post_bundle.sh
  fetch_bundles.sh
  post_bundle.py
  update_bundle.py

src/ledger-spiffe/               ← Hardhat project
  contracts/
    BundleStore.sol
  scripts/
    deploy.js                    ← writes contract address to ../../ledger-spiffe/contract_address.txt
  hardhat.config.js
  package.json

ledger-spiffe/                   ← ledger-specific scripts only
  1_run_creation.sh
  2_run_addition.sh
  3_rotate_key.sh
  post_bundle.sh
  fetch_bundles.sh
  post_bundle.py                 ← web3.py: calls addBundle() tx
  update_bundle.py               ← web3.py: calls updateBundle() tx
  fetch_bundles.py               ← web3.py: eth_call getBundles(), outputs same JSON as Go server
  contract_address.txt           ← runtime artifact (gitignore); written by deploy.js
```

---

## contract_address.txt
`deploy.js` runs once at the start of `1_run_creation.sh`. It deploys `BundleStore.sol` and writes the resulting Ethereum address (e.g. `0xCf7Ed3AccA5a467e9e704C703E8D87F634fB0Fc9`) to `ledger-spiffe/contract_address.txt`. Every Python script reads this file at startup to know which contract to call. File is a runtime artifact — add to `.gitignore`.

---

## Smart Contract: BundleStore.sol

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract BundleStore {
    mapping(string => mapping(string => string)) private bundles;
    mapping(string => string[]) private domains;
    mapping(string => mapping(string => uint256)) private domainIdx; // 1-indexed; 0=absent

    function addBundle(string calldata fed, string calldata td, string calldata raw) external {
        require(domainIdx[fed][td] == 0, "exists");
        bundles[fed][td] = raw;
        domains[fed].push(td);
        domainIdx[fed][td] = domains[fed].length;
    }

    // delete zeros storage slots (SSTORE refund), then write new bundle → measurable gas refund
    function updateBundle(string calldata fed, string calldata td, string calldata raw) external {
        require(domainIdx[fed][td] != 0, "not found");
        delete bundles[fed][td]; // zeros slots → EVM gas refund
        bundles[fed][td] = raw;
    }

    function deleteBundle(string calldata fed, string calldata td) external {
        uint256 idx = domainIdx[fed][td];
        require(idx != 0, "not found");
        string[] storage arr = domains[fed];
        string memory last = arr[arr.length - 1];
        arr[idx - 1] = last;
        domainIdx[fed][last] = idx;
        arr.pop();
        domainIdx[fed][td] = 0;
        delete bundles[fed][td];
    }

    function getBundles(string calldata fed)
        external view
        returns (string[] memory tds, string[] memory raws)
    {
        tds = domains[fed];
        raws = new string[](tds.length);
        for (uint i = 0; i < tds.length; i++) raws[i] = bundles[fed][tds[i]];
    }
}
```

---

## Python Scripts (web3.py)

### Common bootstrap (all three scripts)
```python
from web3 import Web3
import json, pathlib, sys

HARDHAT_RPC = "http://127.0.0.1:8545"
ADDRESS_FILE = pathlib.Path(__file__).parent / "contract_address.txt"
ABI_FILE = pathlib.Path(__file__).parent.parent / "src/ledger-spiffe/artifacts/contracts/BundleStore.sol/BundleStore.json"

w3 = Web3(Web3.HTTPProvider(HARDHAT_RPC))
address = ADDRESS_FILE.read_text().strip()
abi = json.loads(ABI_FILE.read_text())["abi"]
contract = w3.eth.contract(address=address, abi=abi)
account = w3.eth.accounts[0]  # Hardhat default funded account
```

### post_bundle.py
- Reads JSON from stdin: `{"FederationID": ..., "QualifiedBundle": {"TrustDomainName": ..., "RawBundle": ...}}`
- Calls `contract.functions.addBundle(fed, td, raw).transact({"from": account})`
- Prints 201

### update_bundle.py
- Same input format
- Calls `contract.functions.updateBundle(fed, td, raw).transact({"from": account})`
- Prints 200

### fetch_bundles.py
- Argv[1] = federationID
- Calls `contract.functions.getBundles(fed).call()`
- Outputs JSON: `{"QualifiedBundles": [{"TrustDomainName": td, "RawBundle": raw}, ...]}`
- Same shape as Go server → `../common/split_raw_response.py` reused unchanged

---

## Shell Scripts

### 1_run_creation.sh (ledger-spiffe/)
Differences from centralized-repo:
1. Start Hardhat: `npx --prefix src/ledger-spiffe hardhat node --hostname 127.0.0.1 &`
2. Sleep briefly for Hardhat to boot
3. Deploy contract: `npx --prefix src/ledger-spiffe hardhat run scripts/deploy.js --network localhost`
4. No Go server to start

### 2_run_addition.sh / 3_rotate_key.sh
- Nearly identical to centralized-repo; measurement scripts path → `../common/`
- `3_rotate_key.sh`: `update_bundle.py` called from local `./update_bundle.py` (ledger version)

### post_bundle.sh / fetch_bundles.sh
- Same logic as centralized-repo; `split_raw_response.py` path → `../common/split_raw_response.py`

---

## Dependencies
- Node.js + npm; `npm install --save-dev hardhat @nomicfoundation/hardhat-toolbox` inside `src/ledger-spiffe/`
- `pip install web3`

---

## Verification
1. `cd src/ledger-spiffe && npm install && npx hardhat compile` — compiles cleanly
2. `npx hardhat node &` + `npx hardhat run scripts/deploy.js --network localhost` — address written to file
3. `bash ledger-spiffe/1_run_creation.sh 2` — 2-server federation
4. Workload logs show "Experiment begins" → "All messages sent"
5. `bash ledger-spiffe/3_rotate_key.sh 1` — check Hardhat console for gas refund on `updateBundle` tx
6. Workload logs show "Starting special communication" markers
