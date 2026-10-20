#!/usr/bin/env python3
"""Reject private instance data and generated residue from tracked framework source."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ABSOLUTE_USER_PATH = re.compile(
    r"(?:/" + "Users/|/" + r"home/|[A-Za-z]:\\" + r"Users\\)"
)
HIGH_CONFIDENCE_SECRET = re.compile(
    "(?:gh" + r"[pousr]_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)
TEXT_SUFFIXES = {
    ".md", ".json", ".yaml", ".yml", ".toml", ".txt", ".py", ".js", ".css",
    ".html", ".bat", ".vbs", ".command", ".sh", ".ps1",
}
PRIVATE_ARTIFACT_SUFFIXES = {".log", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".mp4", ".mov"}
PRIVATE_PREFIXES = (".local-dashboard/", ".env.local", "dashboard-app/")


def tracked_files() -> list[str]:
    try:
        return subprocess.run(
            ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.splitlines()
    except (OSError, subprocess.CalledProcessError):
        return []


def main() -> int:
    errors: list[str] = []
    tracked = tracked_files()
    for relative in tracked:
        if relative == ".env.local" or relative.startswith(PRIVATE_PREFIXES):
            errors.append(f"private workspace artifact is tracked: {relative}")
    for path in ROOT.rglob("*"):
        relative = path.relative_to(ROOT)
        if ".git" in relative.parts or ".local-dashboard" in relative.parts:
            continue
        if path.name == ".DS_Store" or path.name == "__pycache__" or path.suffix == ".pyc":
            errors.append(f"generated workspace residue stored in repository: {relative}")
        if any(ord(character) > 127 for character in path.name):
            errors.append(f"non-English repository path name: {relative}")
        if path.is_symlink():
            errors.append(f"symlink stored in tracked framework area: {relative}")
            continue
        if path.is_file() and (path.name == "validation-report.json" or "logs" in relative.parts):
            errors.append(f"runtime artifact stored in tracked framework area: {relative}")
        if path.is_file() and path.suffix.lower() in PRIVATE_ARTIFACT_SUFFIXES:
            errors.append(f"project-like binary or log artifact stored in repository: {relative}")
        if not path.is_file() or path.suffix not in TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if ABSOLUTE_USER_PATH.search(text):
            errors.append(f"user-specific absolute path stored in repository: {relative}")
        if HIGH_CONFIDENCE_SECRET.search(text):
            errors.append(f"likely credential stored in repository: {relative}")
        if path.suffix == ".json":
            try:
                value = json.loads(text)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict) and value.get("documentType") in {
                "registered-project", "local-service-dashboard-workspace"
            }:
                errors.append(f"real workspace document stored in repository: {relative}")
    for required in (
        "dashboard/launcher.py",
        "dashboard/project_registry.py",
        "dashboard/repository_status.py",
        "dashboard/ui",
        "defaults/launcher.config.example.json",
        "SKILL.md",
        "AGENTS.md",
        "ARCHITECTURE.md",
        "README.md",
        "launch-dashboard.command",
        "launch-dashboard.bat",
        "launch-dashboard.vbs",
    ):
        if not (ROOT / required).exists():
            errors.append(f"repository is missing required structure: {required}")
    if errors:
        print("Privacy audit failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("OK: tracked framework and ignored local workspace are privacy-isolated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
