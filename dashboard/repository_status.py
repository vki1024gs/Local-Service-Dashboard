#!/usr/bin/env python3
"""Bounded, cached and non-mutating Git status checks for registered projects."""

from __future__ import annotations

import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from process_utils import hidden_process_kwargs


def _run_git(target: Path, args: list[str], timeout: float = 4) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(target), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0"},
        **hidden_process_kwargs(),
    )


def _relation(target: Path, local_head: str, remote_head: str) -> str:
    local_before = _run_git(target, ["merge-base", "--is-ancestor", local_head, remote_head])
    if local_before.returncode == 0:
        return "update_available"
    remote_before = _run_git(target, ["merge-base", "--is-ancestor", remote_head, local_head])
    if remote_before.returncode == 0:
        return "ahead"
    if local_before.returncode == 1 and remote_before.returncode == 1:
        return "diverged"
    return "unknown_relation"


def inspect_repository(target: Path, repository: dict[str, str]) -> dict[str, Any]:
    checked_at = time.time()
    try:
        local = _run_git(target, ["rev-parse", "HEAD"])
        branch = _run_git(target, ["branch", "--show-current"])
        dirty = _run_git(target, ["status", "--porcelain", "--untracked-files=normal"])
        if local.returncode or branch.returncode or dirty.returncode:
            return {"state": "unavailable", "reason": "local_git_unavailable", "checked_at": checked_at}
        local_head = local.stdout.strip()
        current_branch = branch.stdout.strip()
        if not current_branch:
            current_branch = "detached"
        try:
            remote = subprocess.run(
                ["git", "ls-remote", "--heads", repository["url"], repository["branch"]],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
                env={**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0"},
                **hidden_process_kwargs(),
            )
        except subprocess.TimeoutExpired:
            return {
                "state": "unavailable",
                "reason": "remote_timeout",
                "dirty": bool(dirty.stdout.strip()),
                "checked_at": checked_at,
            }
        if remote.returncode != 0:
            return {
                "state": "unavailable",
                "reason": "remote_unavailable",
                "dirty": bool(dirty.stdout.strip()),
                "checked_at": checked_at,
            }
        line = next((item for item in remote.stdout.splitlines() if item.strip()), "")
        if not line:
            return {
                "state": "unavailable",
                "reason": "remote_branch_missing",
                "dirty": bool(dirty.stdout.strip()),
                "checked_at": checked_at,
            }
        remote_head = line.split()[0]
        if remote_head == local_head:
            state = "current"
        else:
            tracking = _run_git(
                target,
                ["rev-parse", f"refs/remotes/{repository['remote']}/{repository['branch']}"],
            )
            state = (
                _relation(target, local_head, remote_head)
                if tracking.returncode == 0 and tracking.stdout.strip() == remote_head
                else "unknown_relation"
            )
        return {
            "state": state,
            "dirty": bool(dirty.stdout.strip()),
            "branch": current_branch,
            "tracked_branch": repository["branch"],
            "url": repository["url"],
            "local_revision": local_head[:12],
            "remote_revision": remote_head[:12],
            "checked_at": checked_at,
        }
    except (OSError, KeyError, subprocess.TimeoutExpired):
        return {"state": "unavailable", "reason": "git_check_failed", "checked_at": checked_at}


class RepositoryStatusMonitor:
    def __init__(self, interval_seconds: float = 0):
        requested_interval = float(interval_seconds)
        self.interval_seconds = 0.0 if requested_interval == 0 else max(30.0, requested_interval)
        self.results: dict[str, dict[str, Any]] = {}
        self.checking: set[str] = set()
        self.lock = threading.Lock()

    def status(
        self,
        project_ref: str,
        target: Path,
        repository: dict[str, str] | None,
        *,
        force: bool = False,
    ) -> dict[str, Any] | None:
        if not repository:
            return None
        now = time.time()
        with self.lock:
            current = self.results.get(project_ref)
            stale = (
                force
                or current is None
                or (
                    self.interval_seconds > 0
                    and now - float(current.get("checked_at", 0)) >= self.interval_seconds
                )
            )
            if stale and project_ref not in self.checking:
                self.checking.add(project_ref)
                threading.Thread(
                    target=self._check,
                    args=(project_ref, target, repository),
                    daemon=True,
                    name=f"repository-status-{project_ref}",
                ).start()
            refreshing = project_ref in self.checking
            if current is None:
                return {"state": "checking", "checked_at": None}
            return {**current, "refreshing": refreshing}

    def _check(self, project_ref: str, target: Path, repository: dict[str, str]) -> None:
        result = inspect_repository(target, repository)
        with self.lock:
            self.results[project_ref] = result
            self.checking.discard(project_ref)
