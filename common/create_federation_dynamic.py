#!/usr/bin/env python3
"""Create a dynamic federation relationship between two servers."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import spire_utils

def create_federation_dynamic(my_num, other_num):
    """
    Create a federation from server my_num to server other_num.

    Args:
        my_num: source server number
        other_num: target server number
    """
    fed_port = spire_utils.fed_port(other_num)
    td = spire_utils.trust_domain(other_num)

    spire_utils.spire_server(
        "federation", "create",
        "-bundleEndpointProfile", "https_spiffe",
        "-trustDomain", td,
        "-bundleEndpointURL", f"https://localhost:{fed_port}",
        "-endpointSpiffeID", f"spiffe://{td}/spire/server",
        server_num=my_num
    )

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: create_federation_dynamic.py <my_num> <other_num>", file=sys.stderr)
        sys.exit(1)

    my_num = int(sys.argv[1])
    other_num = int(sys.argv[2])
    create_federation_dynamic(my_num, other_num)
