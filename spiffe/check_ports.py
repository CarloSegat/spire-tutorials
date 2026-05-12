#!/usr/bin/env python3
"""Check if SPIFFE ledger ports are in use."""

import socket
import subprocess
import sys
from pathlib import Path

def get_process_using_port(port):
    """Get process name/PID using given port."""
    try:
        result = subprocess.run(
            ["lsof", "-i", f":{port}", "-n", "-P"],
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode == 0 and result.stdout:
            lines = result.stdout.strip().split('\n')[1:]  # Skip header
            if lines:
                parts = lines[0].split()
                return f"{parts[0]} (PID {parts[1]})"
    except Exception:
        pass
    return None

def check_port(port):
    """Check if port is listening."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            return s.connect_ex(("127.0.0.1", port)) == 0
    except Exception:
        return False

def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3

    # Hardhat
    print("HARDHAT (8545-8550):")
    for port in range(8545, 8551):
        in_use = check_port(port)
        process = get_process_using_port(port) if in_use else None
        status = f"✗ IN USE ({process})" if process else "✗ IN USE" if in_use else "✓"
        print(f"  {port}: {status}")

    print(f"\nSPIFFE (n={n} clusters):")
    for server_num in range(1, n + 1):
        base_port = 9100 + (server_num * 6 - 5)
        print(f"  Server {server_num} ({base_port}-{base_port + 5}):")

        for offset, name in [
            (0, "SPIRE server"),
            (1, "federation"),
            (2, "workload 1"),
            (3, "workload 2"),
            (4, "workload 3"),
            (5, "workload 4"),
        ]:
            port = base_port + offset
            in_use = check_port(port)
            process = get_process_using_port(port) if in_use else None
            status = f"✗ IN USE ({process})" if process else "✗ IN USE" if in_use else "✓"
            print(f"    {port:5d} ({name:12s}): {status}")

if __name__ == "__main__":
    main()
