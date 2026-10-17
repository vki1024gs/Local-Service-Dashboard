#!/usr/bin/env python3
"""Compatibility entrypoint: initialize this clone instead of copying it."""

from __future__ import annotations

import runpy
from pathlib import Path


if __name__ == "__main__":
    script = Path(__file__).with_name("init_dashboard.py")
    runpy.run_path(str(script), run_name="__main__")
