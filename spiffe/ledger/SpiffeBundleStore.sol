// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title SpiffeBundleStore
/// @notice Mirrors the centralized HTTP bundle repo on-chain.
/// @dev    Bundles are stored as opaque JSON strings keyed by trust domain.
///         updateBundle() deletes-then-writes so SSTORE refund/cost is observable.
contract SpiffeBundleStore {
    mapping(string => string) private bundles;     // td -> raw bundle JSON
    mapping(string => bool)   private bundleExists;
    string[]                  private trustDomains;

    // String args are NOT indexed: with `indexed string` the topic stores only
    // the keccak256 hash, and peers could not recover the trust-domain name
    // from log subscriptions.
    event BundlePosted (string trustDomain);
    event BundleUpdated(string trustDomain);
    event BundleDeleted(string trustDomain);

    function postBundle(string calldata td, string calldata raw) external {
        require(!bundleExists[td], "exists");
        bundles[td] = raw;
        bundleExists[td] = true;
        trustDomains.push(td);
        emit BundlePosted(td);
    }

    /// @notice Update an existing bundle. Explicit delete-then-write keeps
    ///         the SSTORE gas pattern measurable on Hardhat.
    function updateBundle(string calldata td, string calldata raw) external {
        require(bundleExists[td], "missing");
        delete bundles[td];
        bundles[td] = raw;
        emit BundleUpdated(td);
    }

    function deleteBundle(string calldata td) external {
        require(bundleExists[td], "missing");
        delete bundles[td];
        delete bundleExists[td];
        uint n = trustDomains.length;
        for (uint i = 0; i < n; i++) {
            if (keccak256(bytes(trustDomains[i])) == keccak256(bytes(td))) {
                trustDomains[i] = trustDomains[n - 1];
                trustDomains.pop();
                break;
            }
        }
        emit BundleDeleted(td);
    }

    /// @notice Existence check used by the off-chain upsert wrapper.
    function exists(string calldata td) external view returns (bool) {
        return bundleExists[td];
    }

    /// @notice Paginated read of the federation bundle set.
    /// @param offset starting index into trustDomains
    /// @param limit  max bundles to return
    /// @return tds   trust-domain names
    /// @return raws  raw bundle JSONs aligned with tds
    /// @return total total number of bundles currently stored
    function getAllBundles(uint offset, uint limit)
        external view
        returns (string[] memory tds, string[] memory raws, uint total)
    {
        uint n = trustDomains.length;
        total = n;
        uint end = offset + limit;
        if (end > n) end = n;
        uint resultSize = end > offset ? end - offset : 0;
        tds  = new string[](resultSize);
        raws = new string[](resultSize);
        for (uint i = 0; i < resultSize; i++) {
            tds[i]  = trustDomains[offset + i];
            raws[i] = bundles[trustDomains[offset + i]];
        }
    }
}
