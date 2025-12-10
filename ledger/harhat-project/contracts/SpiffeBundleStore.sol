// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract SpiffeBundleStore {
    struct Key {
        string use;
        string kty;
        string crv;
        string x;
        string y;
        string[] x5c;
    }

    struct RawBundle {
        Key[] keys;
        uint256 spiffeSequence;
    }

    struct QualifiedBundle {
        RawBundle rawBundle;
        string trustDomainName;
    }

    QualifiedBundle[] public qualifiedBundles;

    event BundleAdded(uint256 index, string trustDomainName);

    function addBundle(
        string memory trustDomainName,
        uint256 spiffeSequence,
        string memory keyUses,
        string memory keyKtys,
        string memory keyCrvs,
        string memory keyXs,
        string memory keyYs,
        string[] memory x5cs
    ) external {

        // Create bundle in storage directly
        qualifiedBundles.push();
        QualifiedBundle storage qb = qualifiedBundles[
            qualifiedBundles.length - 1
        ];

        qb.trustDomainName = trustDomainName;
        qb.rawBundle.spiffeSequence = spiffeSequence;

      
        qb.rawBundle.keys.push();
        Key storage k = qb.rawBundle.keys[qb.rawBundle.keys.length - 1];

        k.use = keyUses;
        k.kty = keyKtys;
        k.crv = keyCrvs;
        k.x = keyXs;
        k.y = keyYs;

        // Add certificate chain x5c
        for (uint256 j = 0; j < x5cs.length; j++) {
            k.x5c.push(x5cs[j]);
        }
        
        emit BundleAdded(qualifiedBundles.length - 1, trustDomainName);
    }

    function getKeyCount(uint256 bundleIndex) external view returns (uint256) {
        return qualifiedBundles[bundleIndex].rawBundle.keys.length;
    }

    function getAllBundles() external view returns (QualifiedBundle[] memory) {
        return qualifiedBundles;
    }

    function getKey(
        uint256 bundleIndex,
        uint256 keyIndex
    )
        external
        view
        returns (
            string memory use_,
            string memory kty,
            string memory crv,
            string memory x,
            string memory y
        )
    {
        Key storage k = qualifiedBundles[bundleIndex].rawBundle.keys[keyIndex];
        return (k.use, k.kty, k.crv, k.x, k.y);
    }

    function getX5c(
        uint256 bundleIndex,
        uint256 keyIndex
    ) external view returns (string[] memory) {
        return qualifiedBundles[bundleIndex].rawBundle.keys[keyIndex].x5c;
    }
}
