#!/usr/bin/env python3
"""Preview or migrate an old generated Dashboard into the private workspace."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import sys
from pathlib import Path

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "dashboard"))

from project_registry import register_project  # noqa: E402
from validate_config import validate  # noqa: E402
from workspace import atomic_write_bytes, atomic_write_json, operation_lock, require_workspace  # noqa: E402


def old_target(registry: Path, project_ref: str) -> Path:
    link = registry / project_ref
    if link.is_symlink() or link.is_dir():
        return link.resolve(strict=True)
    pointer = registry / f"{project_ref}.path.json"
    value = json.loads(pointer.read_text(encoding="utf-8"))["target"]
    target = Path(value).expanduser()
    return (pointer.parent / target).resolve() if not target.is_absolute() else target.resolve()


def copy_tree(source: Path, destination: Path) -> int:
    if not source.is_dir():
        return 0
    count = sum(1 for item in source.rglob("*") if item.is_file())
    shutil.copytree(source, destination, dirs_exist_ok=True)
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate an existing generated Dashboard instance")
    parser.add_argument("source", type=Path)
    parser.add_argument("--data-dir")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    source = args.source.expanduser().resolve()
    old_dashboard = source / "dashboard"
    if not (old_dashboard / ".launcher-instance").is_file():
        parser.error("source is not an old generated Dashboard instance")
    try:
        workspace = require_workspace(args.data_dir)
    except ValueError as exc:
        parser.error(str(exc))
    config_path = old_dashboard / "launcher.config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    services = config.get("services", [])
    project_refs = sorted({item["project_ref"] for item in services if isinstance(item, dict)})
    registry = old_dashboard / "registry" / "projects"
    registrations = []
    for project_ref in project_refs:
        target = old_target(registry, project_ref)
        visible_record = registry / f"{project_ref}.visible-name"
        visible_name = (
            visible_record.read_text(encoding="utf-8").strip()
            if visible_record.is_file()
            else project_ref.replace("_", "-")
        )
        registrations.append((project_ref, target, visible_name))
    adapter_count = sum(1 for item in (old_dashboard / "adapters").rglob("*") if item.is_file()) if (old_dashboard / "adapters").is_dir() else 0
    entrypoint_count = sum(1 for item in (old_dashboard / "entrypoints").rglob("*") if item.is_file()) if (old_dashboard / "entrypoints").is_dir() else 0
    print(f"SOURCE {source}")
    print(f"TARGET_WORKSPACE {workspace.root}")
    print(f"SERVICES {len(services)}")
    print(f"REGISTRATIONS {len(registrations)}")
    print(f"ADAPTER_FILES {adapter_count}")
    print(f"ENTRYPOINT_FILES {entrypoint_count}")
    print("EXCLUDED runtime, UI, logs, reports, caches and validation artifacts")
    if not args.apply:
        print("DRY_RUN complete; use --apply after reviewing this plan")
        return 0
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = workspace.backups / f"pre-migration-{stamp}"
    with operation_lock(workspace.root):
        backup.mkdir(parents=True, exist_ok=False)
        for source_item, name in (
            (workspace.config, "launcher.config.json"),
            (workspace.registry.parent, "registry"),
            (workspace.projects, "projects"),
            (workspace.adapters, "adapters"),
            (workspace.entrypoints, "entrypoints"),
        ):
            destination = backup / name
            if source_item.is_dir():
                shutil.copytree(source_item, destination, symlinks=True)
            elif source_item.is_file():
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_item, destination)
        try:
            atomic_write_bytes(workspace.config, config_path.read_bytes())
            for project_ref, target, visible_name in registrations:
                register_project(
                    project_ref,
                    target,
                    visible_name=visible_name,
                    replace=(workspace.registry / f"{project_ref}.json").exists(),
                    workspace=workspace,
                    _locked=True,
                )
            copied_adapters = copy_tree(old_dashboard / "adapters", workspace.adapters)
            copied_entrypoints = copy_tree(old_dashboard / "entrypoints", workspace.entrypoints)
            errors = validate(workspace.config)
            if errors:
                raise ValueError("migrated configuration is invalid: " + "; ".join(errors))
        except BaseException:
            for current in (workspace.registry.parent, workspace.projects,
                            workspace.adapters, workspace.entrypoints):
                if current.exists():
                    shutil.rmtree(current)
            for name, destination in (
                ("registry", workspace.registry.parent),
                ("projects", workspace.projects),
                ("adapters", workspace.adapters),
                ("entrypoints", workspace.entrypoints),
            ):
                source_backup = backup / name
                if source_backup.exists():
                    shutil.copytree(source_backup, destination, symlinks=True)
                else:
                    destination.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup / "launcher.config.json", workspace.config)
            raise
    report = {
        "schemaVersion": 1,
        "documentType": "dashboard-instance-migration-report",
        "source": str(source),
        "targetWorkspace": str(workspace.root),
        "services": len(services),
        "registrations": len(registrations),
        "adapterFiles": copied_adapters,
        "entrypointFiles": copied_entrypoints,
        "backup": str(backup),
        "sourcePreserved": True,
        "completedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    report_path = workspace.reports / f"migration-{stamp}.json"
    atomic_write_json(report_path, report)
    print(f"MIGRATED {report_path}")
    print("SOURCE_PRESERVED true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
