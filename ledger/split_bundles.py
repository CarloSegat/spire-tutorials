import json
import sys

if len(sys.argv) < 2:
    raise "need list of bundles"

listofbundles = sys.argv[1]

for l in json.loads(listofbundles):
    td = l["QualifiedBundle"]["TrustDomainName"]
    print(td)
    with open(f"{td}.json", 'w') as fileout:
        fileout.write(json.dumps(l["QualifiedBundle"]["RawBundle"]))