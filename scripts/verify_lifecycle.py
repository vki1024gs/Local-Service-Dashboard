#!/usr/bin/env python3
"""Verify start, sustained health, stop, and restart for generated launchers."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


class StageFailure(RuntimeError):
    def __init__(self, stage: str, message: str):
        super().__init__(message)
        self.stage = stage
        self.result: dict[str, Any] | None = None


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_runtime(launcher_dir: Path):
    path = launcher_dir / "dashboard" / "launcher.py"
    if not path.is_file():
        raise FileNotFoundError(f"launcher.py not found in {launcher_dir}")
    spec = importlib.util.spec_from_file_location("generated_local_service_launcher", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.LOG_DIR = launcher_dir / "dashboard" / "logs"
    return module


def wait_for(manager: Any, service_id: str, predicate: Callable[[dict[str, Any]], bool],
             timeout: float, interval: float, stage: str) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    last = manager.status(service_id)
    while not predicate(last):
        if time.monotonic() >= deadline:
            raise StageFailure(stage, f"timeout after {timeout:g}s; last status={last}")
        time.sleep(interval)
        last = manager.status(service_id)
    return last


def maintain(manager: Any, service_id: str, duration: float, interval: float, stage: str) -> dict[str, Any]:
    deadline = time.monotonic() + duration
    last = manager.status(service_id)
    while time.monotonic() < deadline:
        if not last["running"] or not last["ready"]:
            raise StageFailure(stage, f"service lost health; status={last}")
        time.sleep(min(interval, max(0.05, deadline - time.monotonic())))
        last = manager.status(service_id)
    if not last["running"] or not last["ready"]:
        raise StageFailure(stage, f"service lost health; status={last}")
    return last


def interrupt_for_monitor_test(manager: Any, service_id: str) -> None:
    if hasattr(manager, "interrupt_for_validation"):
        manager.interrupt_for_validation(service_id)
        return
    service = manager.services[service_id]
    process = manager.processes.get(service_id)
    acted = False
    if service.get("stop") is not None:
        manager._run_finite_action(service, "stop")
        acted = True
    if process and process.poll() is None:
        manager._terminate_managed(process)
        acted = True
    if not acted:
        raise StageFailure("monitor-detection", "cannot safely interrupt this test-owned service")


def verify_service(manager: Any, service_id: str, keep_running: bool = False) -> dict[str, Any]:
    service = manager.services[service_id]
    validation = service.get("validation", {})
    startup = float(validation.get("startup_timeout_seconds", 45))
    stability = float(validation.get("stability_seconds", 10))
    shutdown = float(validation.get("shutdown_timeout_seconds", 15))
    monitor_timeout = float(validation.get("monitor_detection_timeout_seconds", 5))
    interval = float(validation.get("poll_interval_seconds", 1))
    stages: list[dict[str, Any]] = []
    result = {"service_id": service_id, "started_at": now(), "passed": False, "stages": stages}

    def record(stage: str, status: dict[str, Any]) -> None:
        stages.append({"stage": stage, "passed": True, "at": now(), "status": status})

    if not service.get("health"):
        raise StageFailure("precondition", "health.url or health.port is required")
    baseline = manager.status(service_id)
    if baseline["running"] or baseline["ready"]:
        raise StageFailure("baseline", "blocked-active: service is already active; request a test window")
    record("baseline", baseline)

    try:
        manager.start(service_id)
        status = wait_for(manager, service_id, lambda value: value["running"] and value["ready"],
                          startup, interval, "start")
        record("start", status)
        record("maintain", maintain(manager, service_id, stability, interval, "maintain"))

        manager.stop(service_id)
        status = wait_for(manager, service_id, lambda value: not value["running"] and not value["ready"],
                          shutdown, interval, "stop")
        record("stop", status)

        manager.start(service_id)
        status = wait_for(manager, service_id, lambda value: value["running"] and value["ready"],
                          startup, interval, "second-start")
        record("second-start", status)

        interrupt_for_monitor_test(manager, service_id)
        status = wait_for(manager, service_id,
                          lambda value: not value["ready"] and value.get("problem") == "stopped-unexpectedly",
                          monitor_timeout, interval, "monitor-detection")
        record("monitor-detection", status)

        manager.start(service_id)
        status = wait_for(manager, service_id,
                          lambda value: value["running"] and value["ready"] and not value.get("problem"),
                          startup, interval, "recovery-start")
        record("recovery-start", status)

        manager.restart(service_id)
        status = wait_for(manager, service_id, lambda value: value["running"] and value["ready"],
                          startup, interval, "restart")
        record("restart", status)
        record("restart-maintain", maintain(manager, service_id, stability, interval, "restart-maintain"))

        if not keep_running:
            manager.stop(service_id)
            status = wait_for(manager, service_id, lambda value: not value["running"] and not value["ready"],
                              shutdown, interval, "cleanup")
            record("cleanup", status)
        result["passed"] = True
        return result
    except StageFailure as exc:
        result.update({"passed": False, "stage": exc.stage, "error": str(exc)})
        exc.result = result
        raise
    except Exception as exc:
        failure = StageFailure(stages[-1]["stage"] if stages else "start", str(exc))
        result.update({"passed": False, "stage": failure.stage, "error": str(failure)})
        failure.result = result
        raise failure from exc
    finally:
        result["finished_at"] = now()
        if not keep_running and service_id in manager.started_by_launcher:
            try:
                manager.stop(service_id)
            except Exception as exc:
                stages.append({"stage": "emergency-cleanup", "passed": False, "at": now(), "error": str(exc)})


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a generated local service launcher")
    parser.add_argument("launcher_dir", type=Path)
    parser.add_argument("--service", action="append", dest="services", help="Service ID; repeat as needed")
    parser.add_argument("--keep-running", action="store_true", help="Leave passing services running")
    parser.add_argument("--report", type=Path,
                        help="Report path (default: launcher_dir/dashboard/validation-report.json)")
    args = parser.parse_args()
    launcher_dir = args.launcher_dir.expanduser().resolve()
    report_path = args.report or launcher_dir / "dashboard" / "validation-report.json"
    report: dict[str, Any] = {"started_at": now(), "launcher_dir": str(launcher_dir), "services": []}
    exit_code = 0
    manager = None
    try:
        runtime = load_runtime(launcher_dir)
        config = runtime.load_config(launcher_dir / "dashboard" / "launcher.config.json")
        manager = runtime.ServiceManager(config)
        report["os"] = runtime.current_os()
        service_ids = args.services or list(manager.services)
        unknown = [item for item in service_ids if item not in manager.services]
        if unknown:
            raise KeyError(f"Unknown service IDs: {', '.join(unknown)}")
        for service_id in service_ids:
            print(f"VERIFY {service_id}")
            try:
                result = verify_service(manager, service_id, args.keep_running)
                report["services"].append(result)
                print(f"PASS {service_id}")
            except StageFailure as exc:
                exit_code = 1
                failure = exc.result or {"service_id": service_id, "passed": False, "stage": exc.stage,
                                         "error": str(exc), "finished_at": now()}
                report["services"].append(failure)
                print(f"FAIL {service_id} [{exc.stage}]: {exc}", file=sys.stderr)
    except Exception as exc:
        exit_code = 2
        report["fatal_error"] = str(exc)
        print(f"ERROR: {exc}", file=sys.stderr)
    finally:
        report["finished_at"] = now()
        report["passed"] = exit_code == 0
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if manager is not None and not args.keep_running:
            manager.stop_all()
        print(f"REPORT {report_path}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
