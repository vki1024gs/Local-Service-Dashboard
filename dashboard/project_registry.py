#!/usr/bin/env python3
"""Versioned private project registration shared by the CLI and runtime."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
import urllib.parse
from pathlib import Path
from typing import Any

from process_utils import hidden_process_kwargs, noninteractive_git_environment
from workspace import (WorkspacePaths, atomic_write_bytes, atomic_write_json, operation_lock,
                       require_workspace)

REF_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
VISIBLE_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
REMOTE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
REGISTRATION_DOCUMENT_TYPE = "registered-project"
REGISTRATION_SCHEMA_VERSION = 1


def _git(target: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-c", "core.askPass=", "-C", str(target), *args],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
            env=noninteractive_git_environment(),
            **hidden_process_kwargs(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def validate_repository_url(value: str) -> str:
    value = value.strip()
    if not value or any(character in value for character in ("\n", "\r", "\0")):
        raise ValueError("repository URL is empty or invalid")
    parsed = urllib.parse.urlsplit(value)
    if parsed.password is not None:
        raise ValueError("repository URL must not contain credentials")
    if parsed.scheme in {"http", "https", "ssh", "git"} and parsed.username and parsed.scheme != "ssh":
        raise ValueError("repository URL must not contain embedded credentials")
    if parsed.query or parsed.fragment:
        raise ValueError("repository URL must not contain query parameters or fragments")
    return value


def validate_repository_web_url(value: str) -> str:
    value = validate_repository_url(value)
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("repository web URL must use http or https")
    return value.rstrip("/")


def repository_web_url(repository: dict[str, str]) -> str | None:
    explicit = repository.get("webUrl")
    if explicit:
        return validate_repository_web_url(explicit)
    clone_url = repository.get("url", "")
    try:
        parsed = urllib.parse.urlsplit(clone_url)
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None
    path = parsed.path[:-4] if parsed.path.endswith(".git") else parsed.path
    if not path or path == "/":
        return None
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, path.rstrip("/"), "", ""))


def validate_repository_names(branch: str, remote: str) -> tuple[str, str]:
    if (not branch or branch.startswith("-") or any(character.isspace() for character in branch)
            or any(token in branch for token in ("..", "@{", "\\", "~", "^", ":", "?", "*", "["))
            or branch.endswith((".", "/")) or "//" in branch):
        raise ValueError("repository branch is invalid")
    if not REMOTE_RE.fullmatch(remote):
        raise ValueError("repository remote name is invalid")
    return branch, remote


def detect_repository(target: Path) -> dict[str, str] | None:
    inside = _git(target, "rev-parse", "--is-inside-work-tree")
    if inside != "true":
        return None
    remote = _git(target, "config", "--get", "branch." + (_git(target, "branch", "--show-current") or "") + ".remote")
    remote = remote or "origin"
    url = _git(target, "remote", "get-url", remote)
    branch = _git(target, "branch", "--show-current")
    if not url or not branch:
        return None
    return {"url": validate_repository_url(url), "branch": branch, "remote": remote}


def registration_path(project_ref: str, workspace: WorkspacePaths) -> Path:
    if not REF_RE.fullmatch(project_ref):
        raise ValueError("project_ref must use lowercase letters, digits, hyphens, or underscores")
    return workspace.registry / f"{project_ref}.json"


def load_registration(project_ref: str, workspace: WorkspacePaths | None = None) -> dict[str, Any]:
    workspace = workspace or require_workspace()
    path = registration_path(project_ref, workspace)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Unregistered project_ref: {project_ref}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid project registration: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"Invalid project registration: {path}")
    expected = {
        "schemaVersion": REGISTRATION_SCHEMA_VERSION,
        "documentType": REGISTRATION_DOCUMENT_TYPE,
        "projectRef": project_ref,
    }
    for key, value in expected.items():
        if data.get(key) != value:
            raise ValueError(f"Registration {project_ref} has invalid {key}")
    target = data.get("target")
    if not isinstance(target, str) or not Path(target).expanduser().is_absolute():
        raise ValueError(f"Registration {project_ref} has an invalid target")
    source_url = data.get("sourceUrl")
    if source_url is not None:
        if not isinstance(source_url, str):
            raise ValueError(f"Registration {project_ref} sourceUrl must be a string")
        validate_repository_web_url(source_url)
    repository = data.get("repository")
    if repository is not None:
        if not isinstance(repository, dict):
            raise ValueError(f"Registration {project_ref} repository must be an object")
        unknown_repository_fields = set(repository) - {"url", "branch", "remote", "webUrl"}
        if unknown_repository_fields:
            raise ValueError(
                f"Registration {project_ref} repository has unknown fields: "
                + ", ".join(sorted(unknown_repository_fields))
            )
        if not all(isinstance(repository.get(key), str) and repository[key] for key in ("url", "branch", "remote")):
            raise ValueError(f"Registration {project_ref} repository metadata is incomplete")
        validate_repository_url(repository["url"])
        validate_repository_names(repository["branch"], repository["remote"])
        if repository.get("webUrl") is not None:
            if not isinstance(repository["webUrl"], str):
                raise ValueError(f"Registration {project_ref} repository webUrl must be a string")
            validate_repository_web_url(repository["webUrl"])
    return data


def resolve_project_ref(project_ref: str, workspace: WorkspacePaths | None = None) -> Path:
    data = load_registration(project_ref, workspace)
    target = Path(data["target"]).expanduser().resolve()
    if not target.is_dir():
        raise FileNotFoundError(f"Project target does not exist: {target}")
    return target


def _remove_shortcut(path: Path) -> None:
    pointer = path.with_suffix(".path.txt")
    if path.is_symlink():
        path.unlink()
    elif path.exists():
        if not path.is_dir():
            raise ValueError(f"Project shortcut is not a directory: {path}")
        os.rmdir(path)
    pointer.unlink(missing_ok=True)


def _create_shortcut(path: Path, target: Path) -> str:
    try:
        os.symlink(os.path.relpath(target, path.parent), path, target_is_directory=True)
        return "LINK"
    except OSError:
        if os.name == "nt":
            result = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(path), str(target)],
                capture_output=True,
                text=True,
                check=False,
                **hidden_process_kwargs(),
            )
            if result.returncode == 0:
                return "JUNCTION"
    path.with_suffix(".path.txt").write_text(str(target) + "\n", encoding="utf-8")
    return "POINTER"


def register_project(
    project_ref: str,
    target: Path,
    *,
    visible_name: str | None = None,
    repository_url: str | None = None,
    repository_web: str | None = None,
    source_url: str | None = None,
    branch: str | None = None,
    remote: str = "origin",
    detect_git: bool = True,
    replace: bool = False,
    workspace: WorkspacePaths | None = None,
    _locked: bool = False,
) -> tuple[dict[str, Any], str]:
    workspace = workspace or require_workspace()
    if not _locked:
        with operation_lock(workspace.root):
            return register_project(
                project_ref, target, visible_name=visible_name, repository_url=repository_url,
                repository_web=repository_web, branch=branch, remote=remote,
                source_url=source_url,
                detect_git=detect_git, replace=replace,
                workspace=workspace, _locked=True,
            )
    path = registration_path(project_ref, workspace)
    target = target.expanduser().resolve()
    if not target.is_dir():
        raise ValueError(f"target is not a directory: {target}")
    visible_name = (visible_name or project_ref.replace("_", "-")).strip()
    if not VISIBLE_RE.fullmatch(visible_name):
        raise ValueError("visible name must use lowercase English kebab-case")
    if path.exists() and not replace:
        raise ValueError("registration exists; pass --replace to update it")
    existing = load_registration(project_ref, workspace) if path.exists() else None
    old_shortcut = workspace.projects / existing["visibleName"] if existing else None
    shortcut = workspace.projects / visible_name
    pointer = shortcut.with_suffix(".path.txt")
    same_shortcut = old_shortcut == shortcut
    if not same_shortcut and (shortcut.exists() or shortcut.is_symlink() or pointer.exists()):
        raise ValueError(f"visible shortcut already exists: {visible_name}")
    repository = None
    if repository_url:
        if not branch:
            raise ValueError("--branch is required with --git-url")
        branch, remote = validate_repository_names(branch, remote)
        repository = {
            "url": validate_repository_url(repository_url),
            "branch": branch,
            "remote": remote,
        }
    elif detect_git:
        repository = detect_repository(target)
        if repository:
            validate_repository_names(repository["branch"], repository["remote"])
    if repository_web:
        if repository is None:
            raise ValueError("--web-url requires Git repository metadata")
        repository["webUrl"] = validate_repository_web_url(repository_web)
    elif repository:
        inferred_web = repository_web_url(repository)
        if inferred_web:
            repository["webUrl"] = inferred_web
    if source_url:
        source_url = validate_repository_web_url(source_url)
    record: dict[str, Any] = {
        "schemaVersion": REGISTRATION_SCHEMA_VERSION,
        "documentType": REGISTRATION_DOCUMENT_TYPE,
        "projectRef": project_ref,
        "visibleName": visible_name,
        "target": str(target),
    }
    if repository:
        record["repository"] = repository
    if source_url:
        record["sourceUrl"] = source_url
    workspace.projects.mkdir(parents=True, exist_ok=True)
    old_record_bytes = path.read_bytes() if path.exists() else None
    if old_record_bytes is not None:
        backup = workspace.backups / "registrations" / f"{project_ref}-{time.time_ns()}.json"
        atomic_write_bytes(backup, old_record_bytes)
    if old_shortcut is not None:
        _remove_shortcut(old_shortcut)
    try:
        kind = _create_shortcut(shortcut, target)
        atomic_write_json(path, record)
    except BaseException:
        _remove_shortcut(shortcut)
        if old_record_bytes is None:
            path.unlink(missing_ok=True)
        else:
            atomic_write_bytes(path, old_record_bytes)
            assert existing is not None
            _create_shortcut(workspace.projects / existing["visibleName"], Path(existing["target"]))
        raise
    return record, kind


def main() -> int:
    parser = argparse.ArgumentParser(description="Register a project with this Dashboard clone")
    parser.add_argument("project_ref")
    parser.add_argument("target", type=Path)
    parser.add_argument("--visible-name")
    parser.add_argument("--git-url")
    parser.add_argument("--web-url")
    parser.add_argument("--source-url")
    parser.add_argument("--branch")
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--no-git", action="store_true")
    parser.add_argument("--replace", action="store_true")
    parser.add_argument("--data-dir")
    args = parser.parse_args()
    try:
        workspace = require_workspace(args.data_dir)
        record, kind = register_project(
            args.project_ref,
            args.target,
            visible_name=args.visible_name,
            repository_url=args.git_url,
            repository_web=args.web_url,
            source_url=args.source_url,
            branch=args.branch,
            remote=args.remote,
            detect_git=not args.no_git,
            replace=args.replace,
            workspace=workspace,
        )
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    tracked = " with Git tracking" if record.get("repository") else ""
    print(f"REGISTERED {record['projectRef']} ({kind}){tracked}")
    print(f"WORKSPACE {workspace.root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
