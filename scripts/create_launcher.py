#!/usr/bin/env python3
"""Materialize a private launcher instance without writing project data into the skill."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = SKILL_ROOT / "assets" / "launcher-template"


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a Local Service Launcher instance")
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    destination = args.destination.expanduser().resolve()
    if destination == SKILL_ROOT or SKILL_ROOT in destination.parents:
        parser.error("destination must be outside the skill directory")
    if destination.exists():
        parser.error("destination already exists; choose an empty new location")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(TEMPLATE, destination, ignore=shutil.ignore_patterns(
        "__pycache__", "*.pyc", "*.log", ".DS_Store", "validation-report.json"
    ))
    internal = destination / "dashboard"
    (destination / "projects").mkdir(exist_ok=True)
    (internal / "logs").mkdir(exist_ok=True)
    (internal / "adapters").mkdir(exist_ok=True)
    (internal / ".launcher-instance").write_text(
        json.dumps({"framework": "local-service-launcher", "schema_version": 1}, indent=2) + "\n",
        encoding="utf-8",
    )
    skill_link = destination / "launcher-skill"
    try:
        os.symlink(os.path.relpath(SKILL_ROOT, destination), skill_link, target_is_directory=True)
    except OSError:
        (destination / "launcher-skill.path.txt").write_text(str(SKILL_ROOT) + "\n", encoding="utf-8")
    print(f"INSTANCE {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
