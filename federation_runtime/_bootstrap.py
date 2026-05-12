"""sys.path bootstrap shared by every federation_runtime module.

Each variant (centralized-spiffe, ledger-spiffe, ...) owns a
`repo_client.py` that speaks the variant's transport (HTTP vs web3 vs ...).
The shared modules import `repo_client` directly. To make that resolution
unambiguous regardless of how the script is invoked, the variant driver
exports `FEDERATION_VARIANT_DIR` into the environment before importing
anything; this module reads it and injects the variant directory into
sys.path so `import repo_client` lands on the right file.

If FEDERATION_VARIANT_DIR is unset, we fall back to the current working
directory so `cd <variant-dir> && python3 <federation_runtime>/foo.py`
also works.
"""

import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _ensure_path(p):
    p = str(p)
    if p not in sys.path:
        sys.path.insert(0, p)


def setup():
    """Inject variant dir, common/, and federation_runtime/ into sys.path."""
    variant_dir = os.environ.get("FEDERATION_VARIANT_DIR") or str(Path.cwd())
    _ensure_path(variant_dir)
    _ensure_path(_REPO_ROOT / "common")
    _ensure_path(_REPO_ROOT / "federation_runtime")


setup()
