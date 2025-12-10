import json
import sys
import requests

if len(sys.argv) < 2:
    raise "need formatted bundle"

r = requests.post("http://localhost:8080/bundle", json=json.loads(sys.argv[1]))
print(r.status_code, r.text)
