import json
import sys
import requests

def upsert_bundle(formatted_bundle_json_str):
    """
    PUT a formatted bundle to the centralized repository (upsert).

    Args:
        formatted_bundle_json_str: JSON string with FederationID and QualifiedBundle

    Returns:
        tuple (status_code, response_text)
    """
    bundle_data = json.loads(formatted_bundle_json_str) if isinstance(formatted_bundle_json_str, str) else formatted_bundle_json_str
    r = requests.put("http://localhost:8080/bundle", json=bundle_data)
    return r.status_code, r.text

if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise RuntimeError("need formatted bundle")

    formatted_bundle = sys.argv[1]
    status, text = upsert_bundle(formatted_bundle)
    print(status, text)
