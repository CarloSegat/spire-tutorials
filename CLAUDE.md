# paper prototype
this porject build a prototype that accompanies a paper.
The prototype represents the implementation of the papr and its goal is to provide the EVALUATION.
the purpose of the paper is to compare different technologies that can be used
to build federations of service providers/ identity providers.
e.g. a federation of hospitals and doctors that provide specialized ML inference,
e.g. a federation of MNO that agree on certain roaming requirements,
e.g. a federation/association of private individuals that agreed to pool hardware to build a shared cloud infra.
The specific use cases don't matter, the goal of the paper is to show how DLT
(dustributed kedger technologies) can help.

# 3 technologies
- **SPIFFE/SPIRE** (already implemented)
- **OAuth 2.0** with token exchange (RFC 8693)
- **OIDC** workload identity federation (OIDC infrastructure reused for M2M)

# EVALUATION - quantitative
- time it takes to create a  federation (x = federation size, y = timein secodns)
- time it takes to add 1 memeber to an existing federation ((x = federation size, y = time in secodns)
- time it takes to rotate a key for 1 memeber (just y = time in seconds)
- time it takes after a key was rotated, to achieve full-mesh communication (i.e. all workloads across all clusters talked to each others)

