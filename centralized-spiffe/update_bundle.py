import json
import sys

import requests

if len(sys.argv) < 2:
    raise "need formatted bundle"

# Use the formatted bundle directly (includes FederationID and QualifiedBundle)
bundle_data = json.loads(sys.argv[1])

r = requests.put("http://localhost:8080/bundle", json=bundle_data)
print(r.status_code, r.text)
