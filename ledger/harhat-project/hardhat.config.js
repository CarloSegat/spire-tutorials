require("@nomicfoundation/hardhat-toolbox");
const { exec } = require('child_process');
const { log } = require("console");

task("deploy", "Depoys the bundle store")
  .addParam("rpc", "KURTOSIS_RPC")
  .addParam("index", "Both server num and index in the prefunded list")
  .setAction(async (taskArgs) => {
    const json = require('./prefunded_addresses.json');

    const provider = new ethers.JsonRpcProvider(taskArgs.rpc);
    const signer = new ethers.Wallet(json[taskArgs.index]['private_key'], provider);

    const Factory = await ethers.getContractFactory("SpiffeBundleStore", signer);

    const store = await Factory.deploy();
    await store.waitForDeployment();

    const addr = await store.getAddress()

    console.log(addr);
  });

task("write_bundle", "Writes bundle to the bundle store")
  .addParam("rpc", "KURTOSIS_RPC")
  .addParam("index", "Both server num and index in the prefunded list")
  .addParam("bundle", "The bundle to write")
  .addParam("contract", "The address of the deployed bundle repository contract")
  .setAction(async (taskArgs) => {
    const json = require('./prefunded_addresses.json');

    const provider = new ethers.JsonRpcProvider(taskArgs.rpc);
    const signer = new ethers.Wallet(json[taskArgs.index]['private_key'], provider);

    const Factory = await ethers.getContractFactory("SpiffeBundleStore", signer);

    const store = await Factory.attach(taskArgs.contract);

    const trustDomainName = `${taskArgs.index}.snet.example`;

    bundle = JSON.parse(taskArgs.bundle)
    const spiffeSequence = bundle.spiffe_sequence;

    x509Keys = bundle.keys.filter((k) => k.use == "x509-svid")[0]

    console.log("\n⏳ Sending addBundle() transaction...");

    const tx = await store.addBundle(
      trustDomainName,
      spiffeSequence,
      x509Keys.use,
      x509Keys.kty,
      x509Keys.crv,
      x509Keys.x,
      x509Keys.y,
      x509Keys.x5c
    );

    await tx.wait();
    console.log("✅ Bundle added!");

  });

task("read_bundles", "Reads all bundles from the bundle store")
  .addParam("rpc", "KURTOSIS_RPC")
  .addParam("index", "Both server num and index in the prefunded list")
  .addParam("contract", "The address of the deployed bundle repository contract")
  .setAction(async (taskArgs) => {
    const json = require('./prefunded_addresses.json');

    const provider = new ethers.JsonRpcProvider(taskArgs.rpc);
    const signer = new ethers.Wallet(json[taskArgs.index]['private_key'], provider);

    const Factory = await ethers.getContractFactory("SpiffeBundleStore", signer);

    const store = await Factory.attach(taskArgs.contract);

    const myTrustDomainName = `${taskArgs.index}.snet.example`;

    const bundles = await store.getAllBundles();
    result = []
    for (let bundle of bundles) {
      building = {}
      building["FederationID"] = "test"
      building["QualifiedBundle"] = {}
      building["QualifiedBundle"]["TrustDomainName"] = bundle[1]

      building["QualifiedBundle"]["RawBundle"] = {}
      building["QualifiedBundle"]["RawBundle"]["spiffe_sequence"] = Number.parseInt(bundle.rawBundle[1])
      building["QualifiedBundle"]["RawBundle"]["keys"] = [{}]

      building["QualifiedBundle"]["RawBundle"]["keys"][0]["use"] = bundle.rawBundle[0][0][0]
      building["QualifiedBundle"]["RawBundle"]["keys"][0]["kty"] = bundle.rawBundle[0][0][1]
      building["QualifiedBundle"]["RawBundle"]["keys"][0]["crv"] = bundle.rawBundle[0][0][2]
      building["QualifiedBundle"]["RawBundle"]["keys"][0]["x"] = bundle.rawBundle[0][0][3]
      building["QualifiedBundle"]["RawBundle"]["keys"][0]["y"] = bundle.rawBundle[0][0][4]
      building["QualifiedBundle"]["RawBundle"]["keys"][0]["x5c"] = [bundle.rawBundle[0][0][5][0]]

      result.push(building)
    }
    console.log(JSON.stringify(result))
  });


const { vars } = require("hardhat/config");

const KURTOSIS_RPC = vars.get("KURTOSIS_RPC", "127.0.0.1:57927");

/** @type import('hardhat/config').HardhatUserConfig */
module.exports = {
  solidity: "0.8.27",
  networks: {
    localnet: {
      url: `http://${KURTOSIS_RPC}`,
      accounts: [
        "bcdf20249abf0ed6d944c0288fad489e33f66b3960d9e6229c1cd214ed3bbe31"
      ],
    },
  }
};
