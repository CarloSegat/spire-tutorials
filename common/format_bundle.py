import json
import sys

if len(sys.argv) < 3:
    raise "need trust domain and the raw bundle"

trust_domain = sys.argv[1]
bundle = json.loads(sys.argv[2])

# print(f"trust_domain {trust_domain}, bundle {bundle}")

raw_bundle = {
    "keys": bundle["keys"],
    "spiffe_sequence": bundle["spiffe_sequence"],
}

json_output = {
    "FederationID": "test",
    "QualifiedBundle": {
        "TrustDomainName": trust_domain,
        "RawBundle": json.dumps(raw_bundle),
    },
}

print(f"{json.dumps(json_output)}")