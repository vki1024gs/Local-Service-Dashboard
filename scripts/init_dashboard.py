#!/usr/bin/env python3
"""Initialize this clone's ignored local Dashboard workspace in place."""

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

from workspace import (  # noqa: E402
    APPLICATION_ID,
    WORKSPACE_DOCUMENT_TYPE,
    WORKSPACE_SCHEMA_VERSION,
    atomic_write_bytes,
    atomic_write_json,
    validate_marker,
    workspace_paths,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize this Dashboard clone in place")
    parser.add_argument("--data-dir")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    paths = workspace_paths(args.data_dir)
    defaults = ROOT / "defaults" / "launcher.config.example.json"
    if paths.marker.exists():
        try:
            validate_marker(paths.marker)
        except ValueError as exc:
            parser.error(str(exc))
        print(f"ALREADY_INITIALIZED {paths.root}")
        return 0
    if paths.root.exists() and (not paths.root.is_dir() or any(paths.root.iterdir())):
        parser.error(
            "workspace contains data but has no valid marker; refusing to overwrite it. "
            "Move it aside or use a different --data-dir."
        )
    if paths.root == ROOT or (ROOT in paths.root.parents and paths.root.name != ".local-dashboard"):
        parser.error("workspace must be .local-dashboard or an explicit directory outside tracked source")
    plan = [
        paths.marker,
        paths.config,
        paths.registry,
        paths.adapters,
        paths.entrypoints,
        paths.projects,
        paths.logs,
        paths.reports,
        paths.cache,
        paths.backups,
        paths.imports,
    ]
    print(f"WORKSPACE {paths.root}")
    for item in plan:
        print(f"CREATE {item.relative_to(paths.root) if item != paths.root else '.'}")
    if args.dry_run:
        print("DRY_RUN complete; no files were changed")
        return 0
    root_existed = paths.root.exists()
    try:
        for directory in (
            paths.registry,
            paths.adapters,
            paths.entrypoints,
            paths.projects,
            paths.logs,
            paths.reports,
            paths.cache,
            paths.backups,
            paths.imports,
        ):
            directory.mkdir(parents=True, exist_ok=True)
        atomic_write_bytes(paths.config, defaults.read_bytes())
        atomic_write_json(
            paths.marker,
            {
                "schemaVersion": WORKSPACE_SCHEMA_VERSION,
                "documentType": WORKSPACE_DOCUMENT_TYPE,
                "applicationId": APPLICATION_ID,
                "createdAt": dt.datetime.now(dt.timezone.utc).isoformat(),
            },
        )
    except BaseException:
        if not root_existed and paths.root.exists():
            shutil.rmtree(paths.root)
        else:
            for item in (paths.marker, paths.config):
                item.unlink(missing_ok=True)
            for directory in reversed((
                paths.registry, paths.adapters, paths.entrypoints, paths.projects,
                paths.logs, paths.reports, paths.cache, paths.backups, paths.imports,
                paths.registry.parent,
            )):
                try:
                    directory.rmdir()
                except OSError:
                    pass
        raise
    print("INITIALIZED in place; no second Dashboard project was created")
    print("GUIDANCE SKILL.md")
    print("NEXT python3 dashboard/project_registry.py <project-ref> <explicit-path>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
