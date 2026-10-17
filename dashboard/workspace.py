#!/usr/bin/env python3
"""Resolve and validate the private Local Service Dashboard workspace."""

from __future__ import annotations

import json
import os
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from typing import Iterator

APPLICATION_ID = "local-service-dashboard"
WORKSPACE_DOCUMENT_TYPE = "local-service-dashboard-workspace"
WORKSPACE_SCHEMA_VERSION = 1
DATA_DIR_ENV = "LOCAL_SERVICE_DASHBOARD_DATA_DIR"
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class WorkspacePaths:
    root: Path
    marker: Path
    config: Path
    registry: Path
    adapters: Path
    entrypoints: Path
    projects: Path
    logs: Path
    reports: Path
    cache: Path
    backups: Path
    imports: Path


def workspace_root(value: str | Path | None = None) -> Path:
    raw = str(value) if value is not None else os.environ.get(DATA_DIR_ENV, ".local-dashboard")
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        candidate = REPOSITORY_ROOT / candidate
    return candidate.resolve()


def workspace_paths(value: str | Path | None = None) -> WorkspacePaths:
    root = workspace_root(value)
    return WorkspacePaths(
        root=root,
        marker=root / "workspace.json",
        config=root / "launcher.config.json",
        registry=root / "registry" / "projects",
        adapters=root / "adapters",
        entrypoints=root / "entrypoints",
        projects=root / "projects",
        logs=root / "logs",
        reports=root / "reports",
        cache=root / "cache",
        backups=root / "backups",
        imports=root / "imports",
    )


def validate_marker(marker: Path) -> dict[str, Any]:
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(
            f"Dashboard workspace is not initialized: {marker}. "
            "Run scripts/init_dashboard.py."
        ) from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid Dashboard workspace marker: {marker}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("Dashboard workspace marker must be an object")
    if data.get("applicationId") != APPLICATION_ID:
        raise ValueError("Dashboard workspace belongs to a different application")
    if data.get("documentType") != WORKSPACE_DOCUMENT_TYPE:
        raise ValueError("Dashboard workspace marker has an unsupported document type")
    if data.get("schemaVersion") != WORKSPACE_SCHEMA_VERSION:
        raise ValueError(
            "Dashboard workspace schema is incompatible; do not overwrite it. "
            "Use a supported migration."
        )
    return data


def require_workspace(value: str | Path | None = None) -> WorkspacePaths:
    paths = workspace_paths(value)
    validate_marker(paths.marker)
    return paths


def atomic_write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def atomic_write_json(path: Path, value: Any) -> None:
    content = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    atomic_write_bytes(path, content.encode("utf-8"))


@contextmanager
def operation_lock(root: Path) -> Iterator[None]:
    """Serialize workspace mutations without guessing whether an old owner is safe to kill."""
    lock = root / ".workspace-operation.lock"
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise ValueError(f"another workspace mutation is active: {lock}") from exc
    try:
        os.write(descriptor, str(os.getpid()).encode("ascii"))
        os.close(descriptor)
        yield
    finally:
        lock.unlink(missing_ok=True)
