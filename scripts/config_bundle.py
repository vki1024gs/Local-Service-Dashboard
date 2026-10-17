#!/usr/bin/env python3
"""Export or import a sanitized, versioned Dashboard configuration bundle."""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "dashboard"))
sys.path.insert(0, str(ROOT / "scripts"))

from project_registry import load_registration, register_project  # noqa: E402
from validate_config import validate  # noqa: E402
from workspace import atomic_write_json, operation_lock, require_workspace, workspace_paths  # noqa: E402

BUNDLE_SCHEMA_VERSION = 1
BUNDLE_DOCUMENT_TYPE = "local-service-dashboard-portable-bundle"
SECRET_RE = re.compile(r"(?i)(password|passwd|secret|token|api[_-]?key|private[_-]?key)\s*[:=]")
ABSOLUTE_USER_PATH_RE = re.compile(
    r"(?:/" + "Users/|/" + r"home/|[A-Za-z]:[\\/](?:" + "Users|Documents" + r")[\\/])"
)


def sanitized_config(config: dict) -> dict:
    result = json.loads(json.dumps(config))
    for service in result.get("services", []):
        service.pop("env", None)
    return result


def export_bundle(output: Path, adapter_names: list[str], data_dir: str | None) -> None:
    workspace = require_workspace(data_dir)
    config = json.loads(workspace.config.read_text(encoding="utf-8"))
    registrations = []
    for project_ref in sorted({item["project_ref"] for item in config.get("services", [])}):
        record = load_registration(project_ref, workspace)
        portable = {"projectRef": project_ref, "visibleName": record["visibleName"]}
        if record.get("repository"):
            portable["repository"] = record["repository"]
        registrations.append(portable)
    adapters = []
    for name in adapter_names:
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"adapter path must stay inside the workspace: {name}")
        source = (workspace.adapters / relative).resolve()
        if workspace.adapters.resolve() not in source.parents or not source.is_file():
            raise ValueError(f"adapter does not exist: {name}")
        content = source.read_bytes()
        text = content.decode("utf-8", errors="ignore")
        if SECRET_RE.search(text) or ABSOLUTE_USER_PATH_RE.search(text):
            raise ValueError(f"adapter appears to contain a secret or machine path: {name}")
        adapters.append({"path": relative.as_posix(), "contentBase64": base64.b64encode(content).decode("ascii")})
    bundle = {
        "schemaVersion": BUNDLE_SCHEMA_VERSION,
        "documentType": BUNDLE_DOCUMENT_TYPE,
        "exportedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
        "config": sanitized_config(config),
        "registrations": registrations,
        "adapters": adapters,
    }
    text = json.dumps(bundle, ensure_ascii=False)
    if SECRET_RE.search(text) or ABSOLUTE_USER_PATH_RE.search(text):
        raise ValueError("portable bundle still contains a likely secret or absolute user path")
    atomic_write_json(output.expanduser().resolve(), bundle)
    print(f"EXPORTED {output.expanduser().resolve()}")


def load_bundle(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schemaVersion") != BUNDLE_SCHEMA_VERSION or data.get("documentType") != BUNDLE_DOCUMENT_TYPE:
        raise ValueError("unsupported configuration bundle")
    if not isinstance(data.get("config"), dict) or not isinstance(data.get("registrations"), list):
        raise ValueError("bundle config or registrations are invalid")
    if SECRET_RE.search(path.read_text(encoding="utf-8")) or ABSOLUTE_USER_PATH_RE.search(path.read_text(encoding="utf-8")):
        raise ValueError("bundle contains a likely secret or absolute user path")
    return data


def parse_mappings(values: list[str]) -> dict[str, Path]:
    mappings: dict[str, Path] = {}
    for value in values:
        project_ref, separator, raw_path = value.partition("=")
        if not separator or not project_ref or not raw_path:
            raise ValueError("--map must use project-ref=/explicit/path")
        target = Path(raw_path).expanduser().resolve()
        if not target.is_dir():
            raise ValueError(f"mapped project path does not exist: {target}")
        mappings[project_ref] = target
    return mappings


def stage_bundle(bundle: dict, mappings: dict[str, Path], root: Path) -> list[str]:
    workspace = workspace_paths(root)
    workspace.root.mkdir(parents=True)
    atomic_write_json(workspace.marker, {
        "schemaVersion": 1,
        "documentType": "local-service-dashboard-workspace",
        "applicationId": "local-service-dashboard",
    })
    for directory in (workspace.registry, workspace.projects, workspace.adapters):
        directory.mkdir(parents=True, exist_ok=True)
    unresolved = []
    for registration in bundle["registrations"]:
        project_ref = registration.get("projectRef")
        target = mappings.get(project_ref)
        if target is None:
            unresolved.append(str(project_ref))
            continue
        repository = registration.get("repository") or {}
        register_project(
            project_ref,
            target,
            visible_name=registration.get("visibleName"),
            repository_url=repository.get("url"),
            repository_web=repository.get("webUrl"),
            branch=repository.get("branch"),
            remote=repository.get("remote", "origin"),
            detect_git=False,
            workspace=workspace,
        )
    atomic_write_json(workspace.config, bundle["config"])
    for adapter in bundle.get("adapters", []):
        relative = Path(adapter.get("path", ""))
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("bundle adapter path escapes the workspace")
        content = base64.b64decode(adapter.get("contentBase64", ""), validate=True)
        destination = workspace.adapters / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
    if not unresolved:
        errors = validate(workspace.config)
        if errors:
            raise ValueError("bundle validation failed: " + "; ".join(errors))
    return unresolved


def import_bundle(path: Path, mappings: dict[str, Path], apply: bool, data_dir: str | None) -> None:
    bundle = load_bundle(path)
    with tempfile.TemporaryDirectory(prefix="dashboard-import-") as temporary:
        unresolved = stage_bundle(bundle, mappings, Path(temporary) / "workspace")
    print(f"SERVICES {len(bundle['config'].get('services', []))}")
    print(f"REGISTRATIONS {len(bundle['registrations'])}")
    print("UNRESOLVED " + (", ".join(unresolved) if unresolved else "none"))
    if unresolved:
        print("PREVIEW_ONLY unresolved projects require explicit --map values; current configuration is unchanged")
        return
    if not apply:
        print("PREVIEW complete; use --apply after reviewing this plan")
        return
    workspace = require_workspace(data_dir)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = workspace.backups / f"pre-import-{stamp}"
    with operation_lock(workspace.root):
        backup.mkdir(parents=True, exist_ok=False)
        for source, name in ((workspace.config, "launcher.config.json"), (workspace.registry.parent, "registry"),
                             (workspace.projects, "projects"), (workspace.adapters, "adapters")):
            destination = backup / name
            if source.is_dir():
                shutil.copytree(source, destination, symlinks=True)
            elif source.is_file():
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
        try:
            for item in workspace.registry.glob("*.json"):
                item.unlink()
            for item in workspace.projects.iterdir():
                if item.is_symlink() or item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)
            for item in workspace.adapters.iterdir():
                if item.is_symlink() or item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)
            atomic_write_json(workspace.config, bundle["config"])
            for registration in bundle["registrations"]:
                repository = registration.get("repository") or {}
                register_project(
                    registration["projectRef"], mappings[registration["projectRef"]],
                    visible_name=registration.get("visibleName"),
                    repository_url=repository.get("url"), repository_web=repository.get("webUrl"),
                    branch=repository.get("branch"),
                    remote=repository.get("remote", "origin"), detect_git=False, workspace=workspace,
                    _locked=True,
                )
            for adapter in bundle.get("adapters", []):
                destination = workspace.adapters / adapter["path"]
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(base64.b64decode(adapter["contentBase64"], validate=True))
            errors = validate(workspace.config)
            if errors:
                raise ValueError("import validation failed: " + "; ".join(errors))
        except BaseException:
            for current in (workspace.registry.parent, workspace.projects, workspace.adapters):
                if current.exists():
                    shutil.rmtree(current)
            shutil.copytree(backup / "registry", workspace.registry.parent, symlinks=True)
            shutil.copytree(backup / "projects", workspace.projects, symlinks=True)
            shutil.copytree(backup / "adapters", workspace.adapters, symlinks=True)
            shutil.copy2(backup / "launcher.config.json", workspace.config)
            raise
    print(f"IMPORTED {path.resolve()}")
    print(f"BACKUP {backup}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir")
    subparsers = parser.add_subparsers(dest="command", required=True)
    export_parser = subparsers.add_parser("export")
    export_parser.add_argument("output", type=Path)
    export_parser.add_argument("--adapter", action="append", default=[])
    import_parser = subparsers.add_parser("import")
    import_parser.add_argument("bundle", type=Path)
    import_parser.add_argument("--map", action="append", default=[])
    import_parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "export":
            export_bundle(args.output, args.adapter, args.data_dir)
        else:
            import_bundle(args.bundle.expanduser().resolve(), parse_mappings(args.map), args.apply, args.data_dir)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
