import json
import sys

def format_bundle(trust_domain, bundle_json_str):
    """
    Format a raw SPIFFE bundle for the centralized repository.

    Args:
        trust_domain: trust domain name (e.g., "1.snet.example")
        bundle_json_str: JSON string of the bundle

    Returns:
        JSON string of the formatted bundle
    """
    bundle = json.loads(bundle_json_str) if isinstance(bundle_json_str, str) else bundle_json_str

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

    return json.dumps(json_output)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        raise RuntimeError("need trust domain and the raw bundle")

    trust_domain = sys.argv[1]
    bundle = sys.argv[2]

    result = format_bundle(trust_domain, bundle)
    print(result)