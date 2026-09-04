#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
CATEGORIES = {"static-web", "frontend", "backend", "service"}
TOP_FIELDS = {"schema_version", "launcher", "services"}
LAUNCHER_FIELDS = {"title", "host", "port", "monitor_interval_seconds", "stop_services_on_exit",
                   "exit_when_no_clients_seconds"}
SERVICE_FIELDS = {"id", "category", "project_ref", "display", "lifecycle", "health", "url", "env",
                  "open_on_start", "validation", "observability", "ports"}
DISPLAY_FIELDS = {"name", "description", "name_from"}
NAME_FROM_FIELDS = {"file", "json_path"}
LIFECYCLE_FIELDS = {"start", "stop", "update"}
HEALTH_FIELDS = {"mode", "url", "host", "port", "timeout_seconds", "env_file", "port_key", "scheme",
                 "path", "fallback_url", "fallback_port", "http_probe_interval_seconds"}
VALIDATION_FIELDS = {"startup_timeout_seconds", "stability_seconds", "shutdown_timeout_seconds",
                     "poll_interval_seconds", "action_timeout_seconds", "monitor_detection_timeout_seconds"}
OBSERVABILITY_FIELDS = {"mode", "url", "host", "env_file", "port_key", "scheme", "path",
                        "fallback_port", "diagnostics_path", "logs_path", "events_path", "open_path"}
PORT_FIELDS = {"name", "mode", "port", "env_file", "port_key", "fallback_port"}


def valid_port(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 65535


def unknown_fields(value: object, allowed: set[str], label: str, errors: list[str]) -> None:
    if isinstance(value, dict):
        for field in sorted(set(value) - allowed):
            errors.append(f"{label}.{field} is not part of framework schema v1")


def validate_command(command: object, label: str, errors: list[str]) -> None:
    if isinstance(command, str):
        return
    if isinstance(command, list):
        if not command or not all(isinstance(item, str) and item for item in command):
            errors.append(f"{label} must be a non-empty string array")
        return
    if isinstance(command, dict):
        unknown_fields(command, {"macos", "windows", "default"}, label, errors)
        if not command:
            errors.append(f"{label} OS map cannot be empty")
        for os_name, value in command.items():
            validate_command(value, f"{label}.{os_name}", errors)
        return
    errors.append(f"{label} must be a string, string array, or OS map")


def registration_target(config_path: Path, project_ref: str) -> Path | None:
    registry = config_path.resolve().parent / "registry" / "projects"
    link = registry / project_ref
    if link.is_dir() or link.is_symlink():
        try:
            return link.resolve(strict=True)
        except OSError:
            return None
    pointer = registry / f"{project_ref}.path.json"
    if not pointer.is_file():
        return None
    try:
        raw = json.loads(pointer.read_text(encoding="utf-8"))["target"]
        target = Path(raw).expanduser()
        return (pointer.parent / target).resolve() if not target.is_absolute() else target.resolve()
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None


def validate(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [str(exc)]
    if not isinstance(data, dict):
        return ["configuration must be an object"]
    unknown_fields(data, TOP_FIELDS, "config", errors)
    if data.get("schema_version") != 1:
        errors.append("schema_version must be 1")

    launcher = data.get("launcher")
    if not isinstance(launcher, dict):
        errors.append("launcher must be an object")
        launcher = {}
    unknown_fields(launcher, LAUNCHER_FIELDS, "launcher", errors)
    if launcher.get("host", "127.0.0.1") not in ("127.0.0.1", "localhost"):
        errors.append("launcher.host must remain local")
    interval = launcher.get("monitor_interval_seconds", 1)
    if not isinstance(interval, (int, float)) or not 0.25 <= interval <= 5:
        errors.append("launcher.monitor_interval_seconds must be between 0.25 and 5")
    if not isinstance(launcher.get("stop_services_on_exit", False), bool):
        errors.append("launcher.stop_services_on_exit must be boolean")
    idle_exit = launcher.get("exit_when_no_clients_seconds", 0)
    if not isinstance(idle_exit, (int, float)) or idle_exit < 0:
        errors.append("launcher.exit_when_no_clients_seconds must be zero or greater")

    services = data.get("services")
    if not isinstance(services, list):
        return errors + ["services must be an array"]
    seen: set[str] = set()
    project_targets: set[Path] = set()
    for index, service in enumerate(services):
        label = f"services[{index}]"
        if not isinstance(service, dict):
            errors.append(f"{label} must be an object")
            continue
        unknown_fields(service, SERVICE_FIELDS, label, errors)
        sid = service.get("id")
        if not isinstance(sid, str) or not ID_RE.fullmatch(sid):
            errors.append(f"{label}.id must match {ID_RE.pattern}")
        elif sid in seen:
            errors.append(f"duplicate service id: {sid}")
        else:
            seen.add(sid)
        category = service.get("category")
        if category not in CATEGORIES:
            errors.append(f"{label}.category must be one of {sorted(CATEGORIES)}")
        project_ref = service.get("project_ref")
        if not isinstance(project_ref, str) or not ID_RE.fullmatch(project_ref):
            errors.append(f"{label}.project_ref is invalid")
        else:
            target = registration_target(path, project_ref)
            if target is None or not target.is_dir():
                errors.append(f"{label}.project_ref is not registered: {project_ref}")
            elif str(target) in json.dumps(service, ensure_ascii=False):
                errors.append(f"{label} duplicates the registered project path; use project_ref and PROJECT_ROOT")
            else:
                project_targets.add(target)

        display = service.get("display")
        if not isinstance(display, dict):
            errors.append(f"{label}.display must be an object")
            display = {}
        unknown_fields(display, DISPLAY_FIELDS, f"{label}.display", errors)
        if not isinstance(display.get("name"), str) and not isinstance(display.get("name_from"), dict):
            errors.append(f"{label}.display needs name or name_from")
        name_from = display.get("name_from")
        if name_from is not None:
            if not isinstance(name_from, dict):
                errors.append(f"{label}.display.name_from must be an object")
            else:
                unknown_fields(name_from, NAME_FROM_FIELDS, f"{label}.display.name_from", errors)
                if not isinstance(name_from.get("file"), str):
                    errors.append(f"{label}.display.name_from.file is required")
                elif Path(name_from["file"]).is_absolute() or ".." in Path(name_from["file"]).parts:
                    errors.append(f"{label}.display.name_from.file must stay inside the project")

        lifecycle = service.get("lifecycle")
        if not isinstance(lifecycle, dict):
            errors.append(f"{label}.lifecycle must be an object")
            lifecycle = {}
        unknown_fields(lifecycle, LIFECYCLE_FIELDS, f"{label}.lifecycle", errors)
        if "start" not in lifecycle:
            errors.append(f"{label}.lifecycle.start is required")
        for action, command in lifecycle.items():
            validate_command(command, f"{label}.lifecycle.{action}", errors)

        health = service.get("health")
        if not isinstance(health, dict):
            errors.append(f"{label}.health must be an object")
            health = {}
        unknown_fields(health, HEALTH_FIELDS, f"{label}.health", errors)
        mode = health.get("mode")
        if mode not in {"http", "tcp", "env", "auto"}:
            errors.append(f"{label}.health.mode must be http, tcp, env, or auto")
        elif mode == "http" and not isinstance(health.get("url"), str):
            errors.append(f"{label}.health.url is required for http mode")
        elif mode == "tcp" and not isinstance(health.get("port"), int):
            errors.append(f"{label}.health.port is required for tcp mode")
        elif mode == "env" and not isinstance(health.get("port_key"), str):
            errors.append(f"{label}.health.port_key is required for env mode")
        if "fallback_port" in health and not isinstance(health["fallback_port"], int):
            errors.append(f"{label}.health.fallback_port must be an integer")
        http_interval = health.get("http_probe_interval_seconds", 0)
        if not isinstance(http_interval, (int, float)) or http_interval < 0:
            errors.append(f"{label}.health.http_probe_interval_seconds must be zero or greater")
        if isinstance(health.get("env_file"), str) and (
            Path(health["env_file"]).is_absolute() or ".." in Path(health["env_file"]).parts
        ):
            errors.append(f"{label}.health.env_file must stay inside the project")

        ports = service.get("ports", [])
        if not isinstance(ports, list):
            errors.append(f"{label}.ports must be an array")
        else:
            port_names: set[str] = set()
            for port_index, binding in enumerate(ports):
                port_label = f"{label}.ports[{port_index}]"
                if not isinstance(binding, dict):
                    errors.append(f"{port_label} must be an object")
                    continue
                unknown_fields(binding, PORT_FIELDS, port_label, errors)
                name = binding.get("name")
                if not isinstance(name, str) or not name.strip():
                    errors.append(f"{port_label}.name must be a non-empty string")
                elif name in port_names:
                    errors.append(f"{label}.ports has duplicate name: {name}")
                else:
                    port_names.add(name)
                binding_mode = binding.get("mode")
                if binding_mode not in {"fixed", "env"}:
                    errors.append(f"{port_label}.mode must be fixed or env")
                elif binding_mode == "fixed" and not valid_port(binding.get("port")):
                    errors.append(f"{port_label}.port must be an integer from 1 to 65535")
                elif binding_mode == "env" and not isinstance(binding.get("port_key"), str):
                    errors.append(f"{port_label}.port_key is required for env mode")
                if "fallback_port" in binding and not valid_port(binding["fallback_port"]):
                    errors.append(f"{port_label}.fallback_port must be an integer from 1 to 65535")
                env_file = binding.get("env_file")
                if isinstance(env_file, str) and (Path(env_file).is_absolute() or ".." in Path(env_file).parts):
                    errors.append(f"{port_label}.env_file must stay inside the project")

        observability = service.get("observability")
        if observability is not None:
            if not isinstance(observability, dict):
                errors.append(f"{label}.observability must be an object")
            else:
                unknown_fields(observability, OBSERVABILITY_FIELDS, f"{label}.observability", errors)
                observability_mode = observability.get("mode")
                if observability_mode not in {"http", "env"}:
                    errors.append(f"{label}.observability.mode must be http or env")
                elif observability_mode == "http" and not isinstance(observability.get("url"), str):
                    errors.append(f"{label}.observability.url is required for http mode")
                elif observability_mode == "env" and not isinstance(observability.get("port_key"), str):
                    errors.append(f"{label}.observability.port_key is required for env mode")
                if isinstance(observability.get("env_file"), str) and (
                    Path(observability["env_file"]).is_absolute()
                    or ".." in Path(observability["env_file"]).parts
                ):
                    errors.append(f"{label}.observability.env_file must stay inside the project")

        validation = service.get("validation", {})
        if not isinstance(validation, dict):
            errors.append(f"{label}.validation must be an object")
        else:
            unknown_fields(validation, VALIDATION_FIELDS, f"{label}.validation", errors)
            for field, value in validation.items():
                if not isinstance(value, (int, float)):
                    errors.append(f"{label}.validation.{field} must be numeric")
            if isinstance(validation.get("stability_seconds"), (int, float)) and validation["stability_seconds"] < 5:
                errors.append(f"{label}.validation.stability_seconds must be at least 5")

    adapters = path.resolve().parent / "adapters"
    if adapters.is_dir():
        for adapter in adapters.rglob("*"):
            if not adapter.is_file() or adapter.name.startswith("."):
                continue
            try:
                text = adapter.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if "PROJECT_ROOT" not in text:
                errors.append(f"adapter must use PROJECT_ROOT instead of a project path: {adapter}")
            for target in project_targets:
                if str(target) in text:
                    errors.append(f"adapter embeds registered project path: {adapter}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("config", type=Path)
    args = parser.parse_args()
    errors = validate(args.config)
    if errors:
        print("Invalid configuration:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(f"OK: {args.config}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
