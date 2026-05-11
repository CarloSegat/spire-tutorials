# Plan: ledger-spiffe

## Context
Mirror `centralized-spiffe/` into `ledger-spiffe/`, replacing the Go HTTP bundle server with a Solidity smart contract on a local Hardhat node. Bundle writes = on-chain transactions; reads = `eth_call` to Hardhat RPC (`http://localhost:8545`). Python scripts use `web3.py`. `updateBundle()` explicitly deletes old storage (SSTORE gas refund) then writes new bundle — enables gas cost measurement on Hardhat.

---

## 1. Rewrite `ledger-spiffe/SpiffeBundleStore.sol`

Current contract is append-only (`addBundle`). Replace entirely with paginated reads for large federations:

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract SpiffeBundleStore {
    mapping(string => string) private bundles;   // td -> raw bundle JSON
    mapping(string => bool)   private exists;
    string[]                  private trustDomains;

    event BundlePosted (string indexed trustDomain);
    event BundleUpdated(string indexed trustDomain);
    event BundleDeleted(string indexed trustDomain);

    function postBundle(string calldata td, string calldata raw) external {
        require(!exists[td], "exists");
        bundles[td] = raw;
        exists[td]  = true;
        trustDomains.push(td);
        emit BundlePosted(td);
    }

    // explicit delete -> SSTORE gas refund, measurable on Hardhat
    function updateBundle(string calldata td, string calldata raw) external {
        require(exists[td], "missing");
        delete bundles[td];
        bundles[td] = raw;
        emit BundleUpdated(td);
    }

    function deleteBundle(string calldata td) external {
        require(exists[td], "missing");
        delete bundles[td];
        delete exists[td];
        for (uint i = 0; i < trustDomains.length; i++) {
            if (keccak256(bytes(trustDomains[i])) == keccak256(bytes(td))) {
                trustDomains[i] = trustDomains[trustDomains.length - 1];
                trustDomains.pop();
                break;
            }
        }
        emit BundleDeleted(td);
    }

    function getAllBundles(uint offset, uint limit)
        external view
        returns (string[] memory tds, string[] memory raws, uint total)
    {
        uint n = trustDomains.length;
        total = n;
        uint end = offset + limit;
        if (end > n) end = n;
        uint resultSize = end > offset ? end - offset : 0;
        tds = new string[](resultSize);
        raws = new string[](resultSize);
        for (uint i = 0; i < resultSize; i++) {
            tds[i] = trustDomains[offset + i];
            raws[i] = bundles[trustDomains[offset + i]];
        }
    }
}
```

---

## 2. Hardhat project at `ledger-spiffe/hardhat/`

**`package.json`**
```json
{
  "name": "spiffe-bundle-store",
  "devDependencies": {
    "hardhat": "^2.22",
    "@nomicfoundation/hardhat-toolbox": "^5"
  }
}
```

**`hardhat.config.js`**
```js
require("@nomicfoundation/hardhat-toolbox");
module.exports = {
  solidity: "0.8.20",
  networks: { hardhat: { mining: { auto: true } } }
};
```

**`scripts/deploy.js`** — deploys and writes address to `../contract_address.txt`
```js
const { ethers } = require("hardhat");
const fs = require("fs");
async function main() {
  const Store = await ethers.getContractFactory("SpiffeBundleStore");
  const store = await Store.deploy();
  await store.waitForDeployment();
  fs.writeFileSync("../contract_address.txt", await store.getAddress());
  console.log("Deployed to:", await store.getAddress());
}
main().catch(e => { console.error(e); process.exit(1); });
```

**`contracts/SpiffeBundleStore.sol`** — symlink to `../SpiffeBundleStore.sol`

---

## 3. `ledger-spiffe/repo_client.py`

Exposes the **same API** as `centralized-spiffe/repo_client.py` so every other script is an unchanged copy. Uses web3.py event filters (not block polling) with 1-second polling interval.

```python
import json, time
from web3 import Web3
from pathlib import Path

RPC_URL       = "http://localhost:8545"
ABI_PATH      = Path(__file__).parent / "hardhat/artifacts/contracts/SpiffeBundleStore.sol/SpiffeBundleStore.json"
ADDR_FILE     = Path(__file__).parent / "contract_address.txt"
FEDERATION_ID = "test"   # kept for API compat

w3 = Web3(Web3.HTTPProvider(RPC_URL))

def _contract():
    abi  = json.loads(ABI_PATH.read_text())["abi"]
    addr = ADDR_FILE.read_text().strip()
    return w3.eth.contract(address=addr, abi=abi)

def _account():
    return w3.eth.accounts[0]

def post_bundle(td: str, raw_bundle: str):
    tx = _contract().functions.postBundle(td, raw_bundle).transact({"from": _account()})
    w3.eth.wait_for_transaction_receipt(tx)
    return (200, "ok")

def upsert_bundle(td: str, raw_bundle: str):
    c = _contract()
    try:
        tx = c.functions.updateBundle(td, raw_bundle).transact({"from": _account()})
    except Exception:
        tx = c.functions.postBundle(td, raw_bundle).transact({"from": _account()})
    w3.eth.wait_for_transaction_receipt(tx)
    return (200, "ok")

def delete_bundle(td: str):
    tx = _contract().functions.deleteBundle(td).transact({"from": _account()})
    w3.eth.wait_for_transaction_receipt(tx)
    return (200, "ok")

def get_bundles():
    c = _contract()
    all_bundles = []
    offset = 0
    limit = 50
    while True:
        tds, raws, total = c.functions.getAllBundles(offset, limit).call()
        if not tds:
            break
        all_bundles.extend(zip(tds, raws))
        if len(all_bundles) >= total:
            break
        offset += limit
    return {"QualifiedBundles": [
        {"TrustDomainName": td, "RawBundle": raw}
        for td, raw in all_bundles
    ]}

def stream_events():
    """Event filters with 1-second polling interval."""
    c = _contract()
    updated_filter = c.events.BundleUpdated.create_filter(fromBlock='latest')
    deleted_filter = c.events.BundleDeleted.create_filter(fromBlock='latest')
    while True:
        for log in updated_filter.get_new_entries():
            yield {"type": "bundle_updated", "data": {"trust_domain": log.args.trustDomain}}
        for log in deleted_filter.get_new_entries():
            yield {"type": "bundle_deleted", "data": {"trust_domain": log.args.trustDomain}}
        time.sleep(1)

def publish_bundle_for_server(server_num, td, raw_bundle, upsert=False):
    if upsert:
        return upsert_bundle(td, raw_bundle)
    return post_bundle(td, raw_bundle)
```

---

## 4. Copy remaining scripts unchanged from `centralized-spiffe/`

All files below are identical copies — they use `repo_client` via relative import and don't touch HTTP directly.

| File | Change needed |
|------|---------------|
| `epoch_io.py` | none |
| `orchestration.py` | none |
| `listen_and_react.py` | none (event filter API identical) |
| `fetch_bundles.py` | none |
| `1_run_creation.py` | **MODIFIED**: Kill+restart Hardhat at start, clear artefacts |
| `2_run_addition.py` | none |
| `3_rotate_key.py` | none |
| `4_run_removal.py` | none |
| `run_self_removal.py` | none |
| `measure_creation_end.py` | none |
| `measure_addition_end.py` | none |
| `measure_rotation_end.py` | none |
| `measure_removal_end.py` | none |

**Critical modifications to `1_run_creation.py`:**
- At the very start (before `setup_n_clusters(n)`): kill any existing Hardhat process and start a fresh node.
- Compile contract: `subprocess.run(["npx", "hardhat", "compile"], cwd="hardhat")`.
- Deploy contract: `subprocess.run(["npx", "hardhat", "run", "scripts/deploy.js", "--network", "localhost"], cwd="hardhat")`.
- Poll for contract address file to be written (max 10s timeout).
- Clear `artefacts/` directory (old logs from previous federation runs).
- Then proceed with normal federation setup.

---

## 5. File summary

| Path | Action |
|------|--------|
| `ledger-spiffe/SpiffeBundleStore.sol` | full rewrite |
| `ledger-spiffe/hardhat/package.json` | new |
| `ledger-spiffe/hardhat/hardhat.config.js` | new |
| `ledger-spiffe/hardhat/scripts/deploy.js` | new |
| `ledger-spiffe/hardhat/contracts/SpiffeBundleStore.sol` | symlink |
| `ledger-spiffe/repo_client.py` | new (web3.py) |
| `ledger-spiffe/{epoch_io,orchestration,...}.py` | copy from `centralized-spiffe/` |

---

## 6. Verification

```bash
# 1. Install dependencies
cd ledger-spiffe/hardhat
npm install

# 2. Run federation creation (self-contained, kills/starts Hardhat)
cd ../..
python ledger-spiffe/1_run_creation.py 2

# 3. Check federation was created
python ledger-spiffe/measure_creation_end.py 2

# 4. Add a cluster
python ledger-spiffe/2_run_addition.py

# 5. Rotate a key
python ledger-spiffe/3_rotate_key.py 1

# 6. Remove a cluster
python ledger-spiffe/4_run_removal.py 1

# 7. Verify measurements
python ledger-spiffe/measure_removal_end.py 1
```
