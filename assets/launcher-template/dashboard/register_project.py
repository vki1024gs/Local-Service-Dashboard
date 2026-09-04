#!/usr/bin/env python3
"""Register a project and create a readable shortcut in the launcher root."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path

REF_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
VISIBLE_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
ROOT = Path(__file__).resolve().parent
INSTANCE_MARKER = ROOT / ".launcher-instance"
PUBLIC_ROOT = ROOT.parent / "projects"


def remove_registration(link: Path, pointer: Path) -> None:
    if link.is_symlink():
        link.unlink()
    elif link.exists():
        if not link.is_dir():
            raise ValueError(f"Registration path is not a directory link: {link}")
        os.rmdir(link)
    if pointer.exists():
        pointer.unlink()


def validate_visible_name(value: str) -> str:
    value = value.strip()
    if not VISIBLE_RE.fullmatch(value):
        raise ValueError("visible name must use lowercase English kebab-case")
    return value


def remove_public_shortcut(name: str) -> None:
    shortcut = PUBLIC_ROOT / name
    pointer = PUBLIC_ROOT / f"{name}.path.txt"
    if shortcut.is_symlink():
        shortcut.unlink()
    elif shortcut.exists():
        if not shortcut.is_dir():
            raise ValueError(f"Visible shortcut path is not a directory link: {shortcut}")
        os.rmdir(shortcut)
    if pointer.exists():
        pointer.unlink()


def create_directory_link(link: Path, target: Path, relative_to: Path) -> str | None:
    try:
        os.symlink(os.path.relpath(target, relative_to), link, target_is_directory=True)
        return "LINK"
    except OSError:
        if os.name == "nt":
            result = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(link), str(target)],
                capture_output=True, text=True, check=False,
            )
            if result.returncode == 0:
                return "JUNCTION"
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Register a project with the launcher framework")
    parser.add_argument("project_ref")
    parser.add_argument("target", type=Path)
    parser.add_argument("--visible-name", help="Readable English folder name under projects")
    parser.add_argument("--replace", action="store_true")
    parser.add_argument("--pointer", action="store_true", help="Use a pointer file instead of a link")
    args = parser.parse_args()
    if not INSTANCE_MARKER.is_file():
        parser.error("not a launcher instance; create it with the skill's create_launcher.py")
    if not REF_RE.fullmatch(args.project_ref):
        parser.error("project_ref must use lowercase letters, digits, hyphens, or underscores")
    target = args.target.expanduser().resolve()
    if not target.is_dir():
        parser.error(f"target is not a directory: {target}")
    try:
        visible_name = validate_visible_name(args.visible_name or args.project_ref.replace("_", "-"))
    except ValueError as exc:
        parser.error(str(exc))
    registry = ROOT / "registry" / "projects"
    registry.mkdir(parents=True, exist_ok=True)
    link = registry / args.project_ref
    pointer = registry / f"{args.project_ref}.path.json"
    visible_record = registry / f"{args.project_ref}.visible-name"
    if (link.exists() or link.is_symlink() or pointer.exists()) and not args.replace:
        parser.error("registration exists; pass --replace to update it")
    if args.replace:
        remove_registration(link, pointer)
        if visible_record.exists():
            remove_public_shortcut(visible_record.read_text(encoding="utf-8").strip())
            visible_record.unlink()

    registration_kind = None
    if not args.pointer:
        registration_kind = create_directory_link(link, target, registry)
    if registration_kind is None:
        pointer.write_text(json.dumps({"target": str(target)}, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
        registration_kind = "POINTER"

    PUBLIC_ROOT.mkdir(parents=True, exist_ok=True)
    public_link = PUBLIC_ROOT / visible_name
    public_pointer = PUBLIC_ROOT / f"{visible_name}.path.txt"
    if public_link.exists() or public_link.is_symlink() or public_pointer.exists():
        parser.error(f"visible shortcut already exists: {visible_name}; choose another --visible-name")
    public_kind = create_directory_link(public_link, target, PUBLIC_ROOT)
    if public_kind is None:
        public_pointer.write_text(str(target) + "\n", encoding="utf-8")
        public_kind = "POINTER"
    visible_record.write_text(visible_name + "\n", encoding="utf-8")
    print(f"{registration_kind} {args.project_ref} -> {target}")
    print(f"VISIBLE_{public_kind} {visible_name} -> {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
