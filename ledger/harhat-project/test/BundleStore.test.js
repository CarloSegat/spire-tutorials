const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("SpiffeBundleStore", function () {

    async function deploy() {
        const Factory = await ethers.getContractFactory("SpiffeBundleStore");
        const store = await Factory.deploy();
        return { store };
    }

    it("should add a bundle and store all values correctly", async function () {
        const { store } = await deploy();

        const trustDomainName = "example.org";
        const spiffeSequence = 42;

        const keyUses = "sig";
        const keyKtys = "EC";
        const keyCrvs = "P-256";
        const keyXs = "x1";
        const keyYs = "y1";
        const x5cFlat = ["certA1", "certA2"];

        await store.addBundle(
            trustDomainName,
            spiffeSequence,
            keyUses,
            keyKtys,
            keyCrvs,
            keyXs,
            keyYs,
            x5cFlat
        );

        expect(await store.getKeyCount(0)).to.equal(1);

        // Key 0
        const key0 = await store.getKey(0, 0);

        expect(key0[0]).to.equal("sig");
        expect(key0[1]).to.equal("EC");


        expect(await store.getX5c(0, 0)).to.deep.equal(["certA1", "certA2"]);

        
    });

});
