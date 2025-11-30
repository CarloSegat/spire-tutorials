import json

with open('response_raw.json', 'r') as raw:
    line = raw.readline()
    j = json.loads(line)
    bundles = j['QualifiedBundles']
    print(bundles)

    for b in bundles:
        print(f"bundle is {b}")
        f = open(b['TrustDomainName'] + '.json', 'w')
        f.write(b['RawBundle'])



