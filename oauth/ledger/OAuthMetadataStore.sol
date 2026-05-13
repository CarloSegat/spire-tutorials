// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title OAuthMetadataStore
/// @notice Mirrors the centralized HTTP metadata repo on-chain.
/// @dev    Metadata is stored as opaque JSON strings keyed by domain name.
///         Uses an index mapping for O(1) deletion (improvement over
///         SpiffeBundleStore's O(n) keccak scan).
contract OAuthMetadataStore {
    mapping(string => string) private metadata;      // domainName -> raw JSON
    mapping(string => bool)   private domainExists;
    mapping(string => uint)   private domainIndex;   // 1-based index into domainNames
    string[]                  private domainNames;

    event DomainAdded  (string domainName);
    event DomainRemoved(string domainName);

    function registerDomain(string calldata domainName, string calldata rawJSON) external {
        require(!domainExists[domainName], "exists");
        metadata[domainName] = rawJSON;
        domainExists[domainName] = true;
        domainNames.push(domainName);
        domainIndex[domainName] = domainNames.length; // 1-based
        emit DomainAdded(domainName);
    }

    function removeDomain(string calldata domainName) external {
        require(domainExists[domainName], "missing");
        // O(1) swap-and-pop using index mapping
        uint idx = domainIndex[domainName] - 1; // convert to 0-based
        uint lastIdx = domainNames.length - 1;
        if (idx != lastIdx) {
            string memory lastDomain = domainNames[lastIdx];
            domainNames[idx] = lastDomain;
            domainIndex[lastDomain] = idx + 1; // back to 1-based
        }
        domainNames.pop();
        delete domainIndex[domainName];
        delete metadata[domainName];
        delete domainExists[domainName];
        emit DomainRemoved(domainName);
    }

    function exists(string calldata domainName) external view returns (bool) {
        return domainExists[domainName];
    }

    function getDomain(string calldata domainName) external view returns (string memory) {
        require(domainExists[domainName], "missing");
        return metadata[domainName];
    }

    /// @notice Paginated read of all registered domains.
    function getAllDomains(uint offset, uint limit)
        external view
        returns (string[] memory names, string[] memory raws, uint total)
    {
        uint n = domainNames.length;
        total = n;
        uint end = offset + limit;
        if (end > n) end = n;
        uint size = end > offset ? end - offset : 0;
        names = new string[](size);
        raws  = new string[](size);
        for (uint i = 0; i < size; i++) {
            string memory dn = domainNames[offset + i];
            names[i] = dn;
            raws[i]  = metadata[dn];
        }
    }
}
