#!/usr/bin/env python3
"""CLI compatibility entrypoint for the shared project registry."""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True

from project_registry import main


if __name__ == "__main__":
    raise SystemExit(main())
