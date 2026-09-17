#!/usr/bin/env python3
"""Reject project-specific artifacts inside the reusable skill package."""

from __future__ import annotations

import json
import re
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = SKILL_ROOT / "assets" / "launcher-template"
ABSOLUTE_USER_PATH = re.compile(r"(?:/Users/|/home/|[A-Za-z]:\\Users\\)")
TEXT_SUFFIXES = {".md", ".json", ".yaml", ".yml", ".toml", ".txt", ".py", ".js", ".css",
                 ".html", ".bat", ".vbs", ".command", ".sh", ".ps1"}
PRIVATE_ARTIFACT_SUFFIXES = {".log", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".mp4", ".mov", ".pdf"}


def main() -> int:
    errors: list[str] = []
    for path in SKILL_ROOT.rglob("*"):
        if path.resolve() == Path(__file__).resolve():
            continue
        relative = path.relative_to(SKILL_ROOT)
        if ".git" in relative.parts:
            continue
        if path.name == ".DS_Store" or path.name == "__pycache__" or path.suffix == ".pyc":
            errors.append(f"generated workspace residue stored in skill: {relative}")
        if TEMPLATE in path.parents and any(ord(character) > 127 for character in path.name):
            errors.append(f"non-English template path name: {relative}")
        if path.is_symlink():
            errors.append(f"symlink stored in skill: {relative}")
            continue
        if path.is_file() and (path.name == "validation-report.json" or "logs" in relative.parts):
            errors.append(f"runtime artifact stored in skill: {relative}")
        if path.is_file() and path.suffix.lower() in PRIVATE_ARTIFACT_SUFFIXES:
            errors.append(f"project-like binary or log artifact stored in skill: {relative}")
        if path.is_file() and path.suffix in TEXT_SUFFIXES:
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if ABSOLUTE_USER_PATH.search(text):
                errors.append(f"user-specific absolute path stored in skill: {relative}")
        if path.is_file() and path.name.endswith(".path.json"):
            try:
                target = json.loads(path.read_text(encoding="utf-8"))["target"]
                if Path(target).expanduser().is_absolute():
                    errors.append(f"absolute project pointer stored in skill: {relative}")
            except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
                errors.append(f"invalid template pointer: {relative}")
    if any(TEMPLATE.rglob(".launcher-instance")):
        errors.append("template must not contain .launcher-instance")
    for required in ("dashboard", "projects", "README.md", "ARCHITECTURE.md", "AGENTS.md",
                     "launch-dashboard.command", "launch-dashboard.bat", "launch-dashboard.vbs"):
        if not (TEMPLATE / required).exists():
            errors.append(f"template is missing required English structure: {required}")
    if errors:
        print("Privacy audit failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("OK: skill contains generic framework data only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
