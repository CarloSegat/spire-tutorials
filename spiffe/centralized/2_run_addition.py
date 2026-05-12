#!/usr/bin/env python3
"""Centralized-variant driver wrapper: dispatches into federation_runtime/run_addition.py."""

import os
import runpy
import sys
from pathlib import Path

VARIANT_DIR = Path(__file__).resolve().parent
os.environ.setdefault("FEDERATION_VARIANT_DIR", str(VARIANT_DIR))
sys.path.insert(0, str(VARIANT_DIR.parent / "federation_runtime"))

runpy.run_module("run_addition", run_name="__main__")
