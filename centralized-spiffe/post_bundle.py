import json
import sys
from pathlib import Path
import requests

# Add common to path
sys.path.insert(0, str(Path(__file__).parent.parent / "common"))
import spire_utils
from print_bundle import print_bundle
from format_bundle import format_bundle

def post_bundle(formatted_bundle_json_str):
    """
    POST a formatted bundle to the centralized repository.

    Args:
        formatted_bundle_json_str: JSON string with FederationID and QualifiedBundle

    Returns:
        tuple (status_code, response_text)
    """
    bundle_data = json.loads(formatted_bundle_json_str) if isinstance(formatted_bundle_json_str, str) else formatted_bundle_json_str
    r = requests.post("http://localhost:8080/bundle", json=bundle_data)
    return r.status_code, r.text

def post_bundle_for_server(server_num):
    """
    Get bundle for a server, format it, and POST to centralized repo.

    Args:
        server_num: server number
    """
    bundle = print_bundle(server_num)
    td = spire_utils.trust_domain(server_num)
    formatted = format_bundle(td, bundle)
    status, text = post_bundle(formatted)
    return status, text

if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise RuntimeError("need formatted bundle")

    formatted_bundle = sys.argv[1]
    status, text = post_bundle(formatted_bundle)
    print(status, text)
