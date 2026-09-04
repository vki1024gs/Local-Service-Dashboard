#!/usr/bin/env python3
"""Stdlib-only local service launcher for Windows and macOS."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import secrets
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "launcher.config.json"
LOG_DIR = ROOT / "logs"
INSTANCE_MARKER = ROOT / ".launcher-instance"
REF_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
LOCAL_URL_RE = re.compile(r"https?://(?:127\.0\.0\.1|localhost|\[::1\])(?::\d+)?[^\s\"']*")


class LauncherHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request: Any, client_address: Any) -> None:
        if isinstance(sys.exc_info()[1], (BrokenPipeError, ConnectionResetError, ConnectionAbortedError)):
            return
        super().handle_error(request, client_address)


class ClientPresence:
    """Track live WebUI event streams and the idle period after the last one leaves."""

    def __init__(self, idle_exit_seconds: float):
        self.idle_exit_seconds = idle_exit_seconds
        self.active_clients = 0
        self.last_zero_at = time.monotonic()
        self.lock = threading.Lock()

    def connected(self) -> None:
        with self.lock:
            self.active_clients += 1

    def disconnected(self) -> None:
        with self.lock:
            self.active_clients = max(0, self.active_clients - 1)
            if self.active_clients == 0:
                self.last_zero_at = time.monotonic()

    def should_exit(self) -> bool:
        with self.lock:
            return (self.idle_exit_seconds > 0 and self.active_clients == 0 and
                    time.monotonic() - self.last_zero_at >= self.idle_exit_seconds)


def stop_server_when_client_idle(server: ThreadingHTTPServer, presence: ClientPresence) -> None:
    while True:
        time.sleep(min(0.5, max(0.05, presence.idle_exit_seconds / 4)))
        if presence.should_exit():
            server.shutdown()
            return


def current_os() -> str:
    return "windows" if os.name == "nt" else "macos"


def expand(value: Any, variables: dict[str, str]) -> Any:
    if isinstance(value, str):
        for key, replacement in variables.items():
            value = value.replace("{" + key + "}", replacement)
        return value
    if isinstance(value, list):
        return [expand(item, variables) for item in value]
    if isinstance(value, dict):
        return {key: expand(item, variables) for key, item in value.items()}
    return value


def select_command(value: Any) -> str | list[str] | None:
    if isinstance(value, dict):
        value = value.get(current_os(), value.get("default"))
    if isinstance(value, str):
        return value
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value
    return None


def resolve_project_ref(config_path: Path, project_ref: str) -> Path:
    if not REF_RE.fullmatch(project_ref):
        raise ValueError(f"Invalid project_ref: {project_ref}")
    registry = config_path.resolve().parent / "registry" / "projects"
    link = registry / project_ref
    if link.is_symlink() or link.is_dir():
        target = link.resolve()
    else:
        pointer = registry / f"{project_ref}.path.json"
        if not pointer.is_file():
            raise FileNotFoundError(f"Unregistered project_ref: {project_ref}")
        raw_target = json.loads(pointer.read_text(encoding="utf-8")).get("target")
        if not isinstance(raw_target, str) or not raw_target:
            raise ValueError(f"Invalid project pointer: {pointer}")
        target = Path(raw_target).expanduser()
        if not target.is_absolute():
            target = (pointer.parent / target).resolve()
    if not target.is_dir():
        raise FileNotFoundError(f"Project target does not exist: {target}")
    return target


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise ValueError("schema_version must be 1")
    if not isinstance(data.get("services"), list):
        raise ValueError("services must be an array")
    ids = [item.get("id") for item in data["services"] if isinstance(item, dict)]
    if any(not value for value in ids) or len(ids) != len(set(ids)):
        raise ValueError("service ids must be present and unique")
    normalized = []
    for raw in data["services"]:
        project_root = resolve_project_ref(path, raw["project_ref"])
        variables = {"launcher_dir": str(path.resolve().parent), "project_root": str(project_root)}
        raw = expand(raw, variables)
        display = raw.get("display", {})
        lifecycle = raw["lifecycle"]
        service = {
            "id": raw["id"], "category": raw["category"], "kind": raw["category"],
            "project_ref": raw["project_ref"], "cwd": str(project_root),
            "name": display.get("name", raw["id"]), "description": display.get("description", ""),
            "display": display, "health": raw["health"], "url": raw.get("url", "auto"),
            "env": raw.get("env", {}), "open_on_start": raw.get("open_on_start", False),
            "validation": raw.get("validation", {}), "observability": raw.get("observability"),
            "ports": raw.get("ports", []),
        }
        service["env"] = {**service["env"], "PROJECT_ROOT": str(project_root)}
        for action in ("start", "stop", "update"):
            if action in lifecycle:
                service[action] = lifecycle[action]
        normalized.append(service)
    data["services"] = normalized
    return data


class ServiceManager:
    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.services = {service["id"]: service for service in config["services"]}
        self.processes: dict[str, subprocess.Popen[bytes]] = {}
        self.logs: dict[str, Any] = {}
        self.started_by_launcher: set[str] = set()
        self.desired_states = {service_id: "unknown" for service_id in self.services}
        self.desired_since: dict[str, float] = {}
        self.observed_active: set[str] = set()
        self.last_state_keys: dict[str, tuple[str, str | None, str]] = {}
        self.last_change_at: dict[str, str] = {}
        self.lock = threading.RLock()
        self.status_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=max(1, min(16, len(self.services))), thread_name_prefix="service-health"
        )
        self.http_health_cache: dict[str, tuple[float, bool]] = {}
        self.health_locks = {service_id: threading.Lock() for service_id in self.services}
        LOG_DIR.mkdir(exist_ok=True)

    def _service(self, service_id: str) -> dict[str, Any]:
        if service_id not in self.services:
            raise KeyError(f"Unknown service: {service_id}")
        return self.services[service_id]

    def _spawn(self, service: dict[str, Any], action: str) -> subprocess.Popen[bytes]:
        command = select_command(service.get(action))
        if command is None:
            raise ValueError(f"{service['name']} has no {action} command for {current_os()}")
        cwd = Path(service["cwd"]).expanduser()
        if not cwd.is_dir():
            raise FileNotFoundError(f"Working directory does not exist: {cwd}")
        env = os.environ.copy()
        env.update({str(k): str(v) for k, v in service.get("env", {}).items()})
        log_path = LOG_DIR / f"{service['id']}.log"
        log_file = open(log_path, "ab", buffering=0)
        log_file.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] {action}: {command!r}\n".encode())
        kwargs: dict[str, Any] = {
            "cwd": str(cwd), "env": env, "stdout": log_file, "stderr": subprocess.STDOUT,
            "shell": isinstance(command, str),
        }
        if os.name == "nt":
            kwargs["creationflags"] = (
                subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
            )
        else:
            kwargs["start_new_session"] = True
        process = subprocess.Popen(command, **kwargs)
        self.logs[service["id"]] = log_file
        return process

    def start(self, service_id: str) -> dict[str, Any]:
        with self.lock:
            service = self._service(service_id)
            if self.status(service_id)["running"]:
                return self.status(service_id)
            self.desired_states[service_id] = "running"
            self.desired_since[service_id] = time.monotonic()
            self.processes[service_id] = self._spawn(service, "start")
            self.started_by_launcher.add(service_id)
        if service.get("open_on_start") and service.get("url"):
            threading.Thread(target=self._open_when_ready, args=(service_id,), daemon=True).start()
        return self.status(service_id)

    def _open_when_ready(self, service_id: str) -> None:
        for _ in range(40):
            time.sleep(0.25)
            status = self.status(service_id)
            if status["ready"]:
                url = self.service_url(self.services[service_id])
                if url:
                    webbrowser.open(url)
                return
            if not status["running"]:
                return

    def _terminate_managed(self, process: subprocess.Popen[bytes]) -> None:
        if process.poll() is not None:
            return
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        else:
            try:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()

    def _run_finite_action(self, service: dict[str, Any], action: str) -> None:
        prior_log = self.logs.pop(service["id"], None)
        if prior_log:
            prior_log.close()
        process = self._spawn(service, action)
        log_file = self.logs.pop(service["id"], None)
        timeout = float(service.get("validation", {}).get("action_timeout_seconds", 30))
        try:
            exit_code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            self._terminate_managed(process)
            raise TimeoutError(f"{action} command exceeded {timeout:g} seconds") from exc
        finally:
            if log_file:
                log_file.close()
        if exit_code != 0:
            raise RuntimeError(f"{action} command exited with code {exit_code}")

    def stop(self, service_id: str) -> dict[str, Any]:
        with self.lock:
            service = self._service(service_id)
            self.desired_states[service_id] = "stopped"
            process = self.processes.get(service_id)
            explicit_stop = select_command(service.get("stop")) is not None
            if explicit_stop:
                self._run_finite_action(service, "stop")
            elif process and process.poll() is None:
                self._terminate_managed(process)
            elif self._ready(service):
                raise RuntimeError("Service is healthy but no stop command or live managed process is available")
            if process and process.poll() is None:
                self._terminate_managed(process)
            log_file = self.logs.pop(service_id, None)
            if log_file:
                log_file.close()
            self.started_by_launcher.discard(service_id)
        return self.status(service_id)

    def restart(self, service_id: str) -> dict[str, Any]:
        self.stop(service_id)
        service = self._service(service_id)
        validation = service.get("validation", {})
        timeout = float(validation.get("shutdown_timeout_seconds", 15))
        interval = float(validation.get("poll_interval_seconds", 1))
        deadline = time.monotonic() + timeout
        while self.status(service_id)["running"]:
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Service did not stop within {timeout:g} seconds")
            time.sleep(interval)
        return self.start(service_id)

    def update(self, service_id: str) -> dict[str, Any]:
        with self.lock:
            service = self._service(service_id)
            if select_command(service.get("update")) is None:
                raise ValueError("No update command configured")
            if self.status(service_id)["running"]:
                raise RuntimeError("Stop the service before updating it")
            self._run_finite_action(service, "update")
            self.desired_states[service_id] = "running"
            self.desired_since[service_id] = time.monotonic()
            self.processes[service_id] = self._spawn(service, "start")
            self.started_by_launcher.add(service_id)

        validation = service.get("validation", {})
        timeout = float(validation.get("startup_timeout_seconds", 45))
        interval = float(validation.get("poll_interval_seconds", 1))
        stability = float(validation.get("stability_seconds", 5))
        deadline = time.monotonic() + timeout
        while not self.status(service_id)["ready"]:
            process = self.processes.get(service_id)
            if process and process.poll() is not None:
                raise RuntimeError(f"Updated service exited with code {process.returncode}")
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Updated service was not ready within {timeout:g} seconds")
            time.sleep(interval)
        stable_until = time.monotonic() + stability
        while time.monotonic() < stable_until:
            if not self.status(service_id)["ready"]:
                raise RuntimeError("Updated service did not remain healthy")
            time.sleep(min(interval, max(0.1, stable_until - time.monotonic())))
        return self.status(service_id)

    def _project_file(self, service: dict[str, Any], relative: str) -> Path:
        root = Path(service["cwd"]).resolve()
        candidate = (root / relative).resolve()
        if candidate != root and root not in candidate.parents:
            raise ValueError(f"Project metadata path escapes project root: {relative}")
        return candidate

    def _display_name(self, service: dict[str, Any]) -> str:
        display = service.get("display", {})
        source = display.get("name_from")
        if isinstance(source, dict):
            try:
                value: Any = json.loads(self._project_file(service, source["file"]).read_text(encoding="utf-8"))
                for part in source.get("json_path", "name").split("."):
                    value = value[part]
                if isinstance(value, str) and value.strip():
                    return value.strip()
            except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
                pass
        return str(display.get("name", service["id"]))

    def _env_value(self, service: dict[str, Any], filename: str, key: str) -> str | None:
        try:
            lines = self._project_file(service, filename).read_text(encoding="utf-8").splitlines()
        except (OSError, ValueError):
            return None
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[7:].lstrip()
            name, separator, value = line.partition("=")
            if separator and name.strip() == key:
                return value.strip().strip("\"'")
        return None

    def _discovered_url(self, service: dict[str, Any]) -> str | None:
        matches = LOCAL_URL_RE.findall(self.log_tail(service["id"]))
        return matches[-1].rstrip(".,);]") if matches else None

    def _endpoint_from_config(self, service: dict[str, Any], config: dict[str, Any]) -> tuple[str, str] | None:
        mode = config.get("mode")
        if mode == "http":
            return ("http", config["url"])
        if mode == "env":
            value = self._env_value(service, config.get("env_file", ".env"), config["port_key"])
            fallback_port = config.get("fallback_port")
            if value is None and fallback_port is None:
                return None
            port = int(value) if value is not None else int(fallback_port)
            host = config.get("host", "127.0.0.1")
            path = "/" + config.get("path", "").lstrip("/")
            return ("http", f"{config.get('scheme', 'http')}://{host}:{port}{path}")
        return None

    def _observability_base_url(self, service: dict[str, Any]) -> str | None:
        config = service.get("observability")
        if not isinstance(config, dict):
            return None
        endpoint = self._endpoint_from_config(service, config)
        return endpoint[1].rstrip("/") if endpoint else None

    def _health_endpoint(self, service: dict[str, Any]) -> tuple[str, Any] | None:
        health = service.get("health")
        if not health:
            return None
        mode = health.get("mode")
        if mode == "http":
            return ("http", health["url"])
        if mode == "tcp":
            return ("tcp", (health.get("host", "127.0.0.1"), int(health["port"])))
        if mode == "env":
            value = self._env_value(service, health.get("env_file", ".env"), health["port_key"])
            fallback_port = health.get("fallback_port")
            if value is None and fallback_port is None:
                return None
            port = int(value) if value is not None else int(fallback_port)
            host = health.get("host", "127.0.0.1")
            if health.get("scheme", "http") == "tcp":
                return ("tcp", (host, port))
            path = "/" + health.get("path", "").lstrip("/")
            return ("http", f"{health.get('scheme', 'http')}://{host}:{port}{path}")
        if mode == "auto":
            discovered = self._discovered_url(service)
            if discovered:
                return ("http", discovered)
            if health.get("fallback_url"):
                return ("http", health["fallback_url"])
            if health.get("fallback_port"):
                return ("tcp", (health.get("host", "127.0.0.1"), int(health["fallback_port"])))
            return None
        if health.get("url"):
            return ("http", health["url"])
        if health.get("port"):
            return ("tcp", (health.get("host", "127.0.0.1"), int(health["port"])))
        return None

    def service_url(self, service: dict[str, Any]) -> str | None:
        configured = service.get("url")
        if isinstance(configured, str) and configured != "auto":
            return configured
        base = self._observability_base_url(service)
        if base:
            open_path = service.get("observability", {}).get("open_path")
            if open_path:
                parsed = urllib.parse.urlparse(base)
                root = f"{parsed.scheme}://{parsed.netloc}"
                return root + "/" + str(open_path).lstrip("/")
        endpoint = self._health_endpoint(service)
        return endpoint[1] if endpoint and endpoint[0] == "http" else None

    def service_port(self, service: dict[str, Any]) -> int | None:
        endpoint = self._health_endpoint(service)
        if endpoint is None:
            return None
        if endpoint[0] == "tcp":
            return int(endpoint[1][1])
        parsed = urllib.parse.urlparse(endpoint[1])
        return parsed.port or (443 if parsed.scheme == "https" else 80)

    def service_ports(self, service: dict[str, Any]) -> list[dict[str, Any]]:
        configured = service.get("ports")
        if not configured:
            port = self.service_port(service)
            return [{"name": "端口", "port": port}] if port is not None else []
        result = []
        for binding in configured:
            port = None
            if binding.get("mode") == "fixed":
                port = int(binding["port"])
            elif binding.get("mode") == "env":
                value = self._env_value(service, binding.get("env_file", ".env"), binding["port_key"])
                fallback = binding.get("fallback_port")
                if value is not None:
                    try:
                        port = int(value)
                    except ValueError:
                        port = None
                elif fallback is not None:
                    port = int(fallback)
            if port is not None:
                result.append({"name": str(binding["name"]), "port": port})
        return result

    def _observability_health(self, service: dict[str, Any]) -> dict[str, Any] | None:
        base = self._observability_base_url(service)
        if not base:
            return None
        path = service.get("observability", {}).get("diagnostics_path", "/diagnostics")
        url = base + "/" + str(path).lstrip("/")
        try:
            with urllib.request.urlopen(url, timeout=float(service.get("health", {}).get("timeout_seconds", 1))) as response:
                if response.status >= 500:
                    return None
                return json.loads(response.read().decode("utf-8"))
        except (OSError, ValueError, TimeoutError, urllib.error.URLError, json.JSONDecodeError):
            return None

    def _ready(self, service: dict[str, Any]) -> bool:
        observed = self._observability_health(service)
        if isinstance(observed, dict):
            service["_last_observability_health"] = observed
            return bool(observed.get("ready") or observed.get("status") == "ready")
        health = service.get("health", {})
        endpoint = self._health_endpoint(service)
        if endpoint is None:
            return False
        timeout = float(health.get("timeout_seconds", 1))
        if endpoint[0] == "http":
            interval = float(health.get("http_probe_interval_seconds", 0))
            with self.health_locks[service["id"]]:
                if interval > 0:
                    parsed = urllib.parse.urlparse(endpoint[1])
                    port = parsed.port or (443 if parsed.scheme == "https" else 80)
                    try:
                        with socket.create_connection((parsed.hostname, port), timeout):
                            pass
                    except (OSError, ValueError, TypeError):
                        self.http_health_cache.pop(service["id"], None)
                        return False
                    cached_at, cached_ready = self.http_health_cache.get(service["id"], (0.0, False))
                    if cached_ready and time.monotonic() - cached_at < interval:
                        return True
                try:
                    with urllib.request.urlopen(endpoint[1], timeout=timeout) as response:
                        ready = response.status < 500
                except (urllib.error.URLError, TimeoutError, ValueError):
                    ready = False
                self.http_health_cache[service["id"]] = (time.monotonic(), ready)
                return ready
        try:
            with socket.create_connection(endpoint[1], timeout):
                return True
        except (OSError, ValueError, KeyError, TypeError):
            return False

    def status(self, service_id: str) -> dict[str, Any]:
        service = self._service(service_id)
        ready = self._ready(service)
        with self.lock:
            process = self.processes.get(service_id)
            exit_code = process.poll() if process else None
            managed_running = bool(process and exit_code is None)
            running = managed_running or ready
            desired = self.desired_states[service_id]
            if ready:
                self.observed_active.add(service_id)
            validation = service.get("validation", {})
            startup_timeout = float(validation.get("startup_timeout_seconds", 45))
            desired_age = time.monotonic() - self.desired_since.get(service_id, time.monotonic())
            expected_running = desired == "running" or (desired == "unknown" and service_id in self.observed_active)
            problem = None
            if expected_running and not ready:
                if service_id in self.observed_active:
                    problem = "health-check-failed" if managed_running else "stopped-unexpectedly"
                elif desired == "running" and desired_age >= startup_timeout:
                    problem = "startup-timeout"
            if problem:
                state = "startup-timeout" if problem == "startup-timeout" else (
                    "unhealthy" if managed_running else "stopped-unexpectedly"
                )
            elif ready:
                state = "ready"
            elif desired == "stopped" and running:
                state = "stopping"
            elif managed_running or desired == "running":
                state = "starting"
            else:
                state = "stopped"
            state_key = (state, problem, desired)
            if self.last_state_keys.get(service_id) != state_key:
                self.last_state_keys[service_id] = state_key
                self.last_change_at[service_id] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
            if process and not managed_running:
                log_file = self.logs.pop(service_id, None)
                if log_file:
                    log_file.close()
        return {
            "id": service_id,
            "running": running,
            "ready": ready,
            "pid": process.pid if managed_running else None,
            "exit_code": exit_code,
            "state": state,
            "problem": problem,
            "desired": desired,
            "last_change_at": self.last_change_at.get(service_id),
        }

    def public_services(self) -> list[dict[str, Any]]:
        services = list(self.services.values())
        statuses = list(self.status_pool.map(lambda item: self.status(item["id"]), services))
        names = {service["id"]: self._display_name(service) for service in services}
        ports = {service["id"]: self.service_ports(service) for service in services}
        owners: dict[int, set[str]] = {}
        for service in services:
            for binding in ports[service["id"]]:
                owners.setdefault(binding["port"], set()).add(service["id"])
        result = []
        for service, status in zip(services, statuses):
            item = {key: service.get(key) for key in ("id", "description", "kind")}
            item["name"] = names[service["id"]]
            item["url"] = self.service_url(service)
            item["port"] = self.service_port(service)
            item["ports"] = []
            item["port_conflicts"] = []
            for binding in ports[service["id"]]:
                other_ids = sorted(owners[binding["port"]] - {service["id"]})
                public_binding = {**binding, "conflict": bool(other_ids),
                                  "conflicts_with": [names[other_id] for other_id in other_ids]}
                item["ports"].append(public_binding)
                if other_ids:
                    item["port_conflicts"].append({
                        "port": binding["port"],
                        "with": [names[other_id] for other_id in other_ids],
                    })
            item["can_update"] = select_command(service.get("update")) is not None
            item.update(status)
            if service.get("_last_observability_health"):
                item["health"] = service["_last_observability_health"]
            result.append(item)
        return result

    def log_tail(self, service_id: str, limit: int = 24000) -> str:
        service = self._service(service_id)
        observed = self._observability_log_tail(service)
        if observed is not None:
            return observed
        path = LOG_DIR / f"{service_id}.log"
        if not path.exists():
            return ""
        with open(path, "rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - limit))
            return handle.read().decode("utf-8", errors="replace")

    def _observability_log_tail(self, service: dict[str, Any]) -> str | None:
        base = self._observability_base_url(service)
        if not base:
            return None
        path = service.get("observability", {}).get("logs_path", "/logs")
        url = base + "/" + str(path).lstrip("/") + "?limit=300"
        try:
            with urllib.request.urlopen(url, timeout=float(service.get("health", {}).get("timeout_seconds", 1))) as response:
                if response.status >= 500:
                    return None
                payload = json.loads(response.read().decode("utf-8"))
        except (OSError, ValueError, TimeoutError, urllib.error.URLError, json.JSONDecodeError):
            return None
        events = payload.get("events", [])
        lines = []
        for event in events:
            timestamp = event.get("timestamp", "")
            level = str(event.get("level", "info")).upper().ljust(7)
            module = event.get("module") or event.get("type") or "-"
            message = event.get("message") or event.get("type") or ""
            lines.append(f"[{timestamp}] {level} {module}: {message}")
        return "\n".join(lines)

    def stop_all(self) -> None:
        for service_id in list(self.started_by_launcher):
            self.stop(service_id)


def make_handler(manager: ServiceManager, token: str, title: str, monitor_interval: float = 1.0,
                 presence: ClientPresence | None = None):
    class Handler(SimpleHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def __init__(self, *args: Any, **kwargs: Any):
            super().__init__(*args, directory=str(ROOT / "ui"), **kwargs)

        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def end_headers(self) -> None:
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            super().end_headers()

        def _json(self, status: int, payload: Any) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _authorized(self) -> bool:
            return secrets.compare_digest(self.headers.get("X-Launcher-Token", ""), token)

        def _monitor_stream(self) -> None:
            if presence is not None:
                presence.connected()
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "keep-alive")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()
            sequence = 0
            try:
                while True:
                    sequence += 1
                    payload = {"sequence": sequence, "observed_at": time.time(),
                               "services": manager.public_services()}
                    self.wfile.write((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))
                    self.wfile.flush()
                    time.sleep(monitor_interval)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                return
            finally:
                if presence is not None:
                    presence.disconnected()

        def do_GET(self) -> None:
            if self.path == "/api/bootstrap":
                self._json(200, {"token": token, "title": title})
                return
            if self.path == "/api/events":
                if not self._authorized():
                    self._json(403, {"error": "Forbidden"})
                else:
                    self._monitor_stream()
                return
            if self.path == "/api/services":
                if not self._authorized():
                    self._json(403, {"error": "Forbidden"})
                else:
                    self._json(200, manager.public_services())
                return
            if self.path.startswith("/api/logs/"):
                if not self._authorized():
                    self._json(403, {"error": "Forbidden"})
                else:
                    try:
                        self._json(200, {"log": manager.log_tail(self.path.removeprefix("/api/logs/"))})
                    except KeyError as exc:
                        self._json(404, {"error": str(exc)})
                return
            super().do_GET()

        def do_POST(self) -> None:
            if not self._authorized():
                self._json(403, {"error": "Forbidden"})
                return
            if self.path == "/api/shutdown":
                self._json(202, {"status": "shutting-down"})
                threading.Thread(target=self.server.shutdown, daemon=True,
                                 name="webui-user-shutdown").start()
                return
            parts = self.path.strip("/").split("/")
            if len(parts) != 3 or parts[0] != "api":
                self._json(404, {"error": "Not found"})
                return
            _, action, service_id = parts
            try:
                if action not in ("start", "stop", "restart", "update"):
                    raise ValueError("Unsupported action")
                self._json(200, getattr(manager, action)(service_id))
            except KeyError as exc:
                self._json(404, {"error": str(exc)})
            except Exception as exc:
                self._json(409, {"error": str(exc)})

    return Handler


def main() -> int:
    parser = argparse.ArgumentParser(description="Local Service Launcher")
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--check-config", action="store_true")
    args = parser.parse_args()
    try:
        config = load_config(args.config)
    except Exception as exc:
        print(f"Configuration error: {exc}")
        return 2
    if args.check_config:
        print(f"OK: {args.config} ({len(config['services'])} services, {current_os()})")
        return 0
    if not INSTANCE_MARKER.is_file():
        print("Refusing to run the reusable template; create a launcher instance first")
        return 2
    launcher = config.get("launcher", {})
    host = launcher.get("host", "127.0.0.1")
    if host not in ("127.0.0.1", "localhost"):
        print("Refusing non-local host; use 127.0.0.1 or localhost")
        return 2
    port = int(launcher.get("port", 17321))
    title = launcher.get("title", "Local Service Launcher")
    monitor_interval = float(launcher.get("monitor_interval_seconds", 1))
    idle_exit_seconds = float(launcher.get("exit_when_no_clients_seconds", 0))
    manager = ServiceManager(config)
    token = secrets.token_urlsafe(32)
    presence = ClientPresence(idle_exit_seconds) if idle_exit_seconds > 0 else None
    server = LauncherHTTPServer((host, port), make_handler(manager, token, title, monitor_interval, presence))
    if presence is not None:
        threading.Thread(target=stop_server_when_client_idle, args=(server, presence),
                         daemon=True, name="webui-idle-exit").start()
    url = f"http://{host}:{server.server_port}/"
    print(f"{title}: {url}")
    if not args.no_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        if launcher.get("stop_services_on_exit", False):
            manager.stop_all()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
