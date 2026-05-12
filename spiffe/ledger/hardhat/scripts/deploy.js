const { ethers } = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  const Store = await ethers.getContractFactory("SpiffeBundleStore");
  const store = await Store.deploy();
  await store.waitForDeployment();
  const addr = await store.getAddress();
  const out = path.resolve(__dirname, "..", "..", "contract_address.txt");
  fs.writeFileSync(out, addr);
  console.log("Deployed to:", addr);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
