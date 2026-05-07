#!/usr/bin/env python3
"""Print SPIFFE bundle for a server."""

import sys
from pathlib import Path

# Add parent dir to path to import spire_utils
sys.path.insert(0, str(Path(__file__).parent))
import spire_utils

def print_bundle(server_num):
    """Get SPIFFE bundle for a server."""
    return spire_utils.spire_server("bundle", "show", "-format", "spiffe", server_num=server_num)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: print_bundle.py <server_num>", file=sys.stderr)
        sys.exit(1)

    server_num = int(sys.argv[1])
    bundle = print_bundle(server_num)
    print(bundle)
