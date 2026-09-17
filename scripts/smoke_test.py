#!/usr/bin/env python3
import importlib.util
import json
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from unittest import mock

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "assets" / "launcher-template"
LAUNCHER = TEMPLATE / "dashboard" / "launcher.py"
CREATE_LAUNCHER = ROOT / "scripts" / "create_launcher.py"
REGISTER_PROJECT = TEMPLATE / "dashboard" / "register_project.py"
assert LAUNCHER.is_file()
assert not any(any(ord(character) > 127 for character in path.name) for path in TEMPLATE.rglob("*"))

register_spec = importlib.util.spec_from_file_location("register_project", REGISTER_PROJECT)
register_project = importlib.util.module_from_spec(register_spec)
assert register_spec.loader
register_spec.loader.exec_module(register_project)
assert register_project.validate_visible_name("synthetic-project") == "synthetic-project"
try:
    register_project.validate_visible_name("Synthetic Project")
    raise AssertionError("non-kebab visible names must be rejected")
except ValueError:
    pass

with tempfile.TemporaryDirectory() as temp:
    destination = Path(temp) / "synthetic-launcher"
    subprocess.run([sys.executable, str(CREATE_LAUNCHER), str(destination)], check=True,
                   capture_output=True, text=True)
    assert (destination / "dashboard" / ".launcher-instance").is_file()
    assert (destination / "projects").is_dir()
    assert (destination / "launcher-skill").exists() or (destination / "launcher-skill.path.txt").is_file()
    assert (destination / "launch-dashboard.command").is_file()
    assert (destination / "launch-dashboard.bat").is_file()
    windows_launcher = destination / "launch-dashboard.vbs"
    assert windows_launcher.is_file()
    assert "pythonw.exe" in windows_launcher.read_text(encoding="utf-8").lower()
    batch_launcher = (destination / "launch-dashboard.bat").read_text(encoding="utf-8").lower()
    assert "wscript.exe" in batch_launcher
    assert "dashboard\\launcher.py" not in batch_launcher
    assert (destination / "README.md").is_file()
    if sys.platform == "win32":
        launch_marker = destination / "windows-launch-ok.txt"
        (destination / "dashboard" / "launcher.py").write_text(
            "import os, tempfile\n"
            "from pathlib import Path\n"
            "os.chdir(tempfile.gettempdir())\n"
            f"Path({str(launch_marker)!r}).write_text('ok', encoding='utf-8')\n",
            encoding="utf-8",
        )
        windows_launch = subprocess.run(
            ["cscript.exe", "//nologo", str(windows_launcher)],
            capture_output=True,
            text=True,
        )
        assert windows_launch.returncode == 0, windows_launch.stdout + windows_launch.stderr
        deadline = time.monotonic() + 5
        while not launch_marker.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert launch_marker.read_text(encoding="utf-8") == "ok"
        time.sleep(0.5)
print("OK: English-only materialized framework structure")
spec = importlib.util.spec_from_file_location("launcher", LAUNCHER)
launcher = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(launcher)

VERIFY = ROOT / "scripts" / "verify_lifecycle.py"
verify_spec = importlib.util.spec_from_file_location("verify_lifecycle", VERIFY)
verify = importlib.util.module_from_spec(verify_spec)
assert verify_spec.loader
verify_spec.loader.exec_module(verify)

with tempfile.TemporaryDirectory() as temp:
    root = Path(temp)
    project = root / "project"
    project.mkdir()
    registry = root / "registry" / "projects"
    registry.mkdir(parents=True)
    (registry / "probe.path.json").write_text(json.dumps({"target": str(project)}), encoding="utf-8")
    launcher.LOG_DIR = root / "logs"
    path = root / "launcher.config.json"
    path.write_text(json.dumps({
        "schema_version": 1,
        "launcher": {},
        "services": [{"id": "probe", "category": "service", "project_ref": "probe",
                      "display": {"name": "Probe"},
                      "lifecycle": {
                          "start": {"default": [sys.executable, "-c", "import time; time.sleep(30)"]},
                          "stop": {"default": [sys.executable, "-c", "pass"]}},
                      "health": {"mode": "tcp", "port": 1}}]
    }), encoding="utf-8")
    config = launcher.load_config(path)
    manager = launcher.ServiceManager(config)
    assert manager.services["probe"]["cwd"] == str(project)
    assert manager.services["probe"]["env"]["PROJECT_ROOT"] == str(project)
    assert manager.start("probe")["running"]
    assert manager.stop("probe")["running"] is False
    if sys.platform == "win32":
        with mock.patch.object(launcher.subprocess, "Popen") as popen:
            popen.return_value.pid = 1234
            popen.return_value.poll.return_value = None
            manager.start("probe")
            creationflags = popen.call_args.kwargs["creationflags"]
            manager.logs["probe"].close()
            assert creationflags & subprocess.CREATE_NEW_PROCESS_GROUP
            assert creationflags & subprocess.CREATE_NO_WINDOW
print("OK: launcher process lifecycle")

with tempfile.TemporaryDirectory() as temp:
    root = Path(temp)
    project = root / "project"
    project.mkdir()
    (project / "package.json").write_text('{"name":"alpha-ui"}', encoding="utf-8")
    (project / ".env").write_text("PORT=3100\n", encoding="utf-8")
    registry = root / "registry" / "projects"
    registry.mkdir(parents=True)
    (registry / "web.path.json").write_text(json.dumps({"target": str(project)}), encoding="utf-8")
    path = root / "launcher.config.json"
    path.write_text(json.dumps({"schema_version": 1, "launcher": {}, "services": [{
        "id": "web", "category": "frontend", "project_ref": "web",
        "display": {"name": "fallback", "name_from": {"file": "package.json", "json_path": "name"}},
        "lifecycle": {"start": [sys.executable, "-c", "pass"]},
        "health": {"mode": "env", "env_file": ".env", "port_key": "PORT", "scheme": "http"},
        "url": "auto"
    }]}), encoding="utf-8")
    launcher.LOG_DIR = root / "logs"
    manager = launcher.ServiceManager(launcher.load_config(path))
    service = manager.services["web"]
    assert manager._display_name(service) == "alpha-ui"
    assert manager.service_url(service) == "http://127.0.0.1:3100/"
    (project / "package.json").write_text('{"name":"beta-ui"}', encoding="utf-8")
    (project / ".env").write_text("PORT=4200\n", encoding="utf-8")
    assert manager._display_name(service) == "beta-ui"
    assert manager.service_url(service) == "http://127.0.0.1:4200/"
print("OK: project-owned name and port drift")

with tempfile.TemporaryDirectory() as temp:
    root = Path(temp)
    project = root / "project"
    project.mkdir()
    (project / ".env").write_text("# PORT intentionally omitted\n", encoding="utf-8")
    registry = root / "registry" / "projects"
    registry.mkdir(parents=True)
    (registry / "web.path.json").write_text(json.dumps({"target": str(project)}), encoding="utf-8")
    path = root / "launcher.config.json"
    path.write_text(json.dumps({"schema_version": 1, "launcher": {}, "services": [{
        "id": "web", "category": "backend", "project_ref": "web",
        "display": {"name": "Synthetic service"},
        "lifecycle": {"start": [sys.executable, "-c", "pass"]},
        "health": {"mode": "env", "env_file": ".env", "port_key": "PORT",
                   "scheme": "http", "fallback_port": 54321},
        "url": "auto"
    }]}), encoding="utf-8")
    launcher.LOG_DIR = root / "logs"
    manager = launcher.ServiceManager(launcher.load_config(path))
    service = manager.services["web"]
    assert manager.service_url(service) == "http://127.0.0.1:54321/"
    (project / ".env").write_text("PORT=54322\n", encoding="utf-8")
    assert manager.service_url(service) == "http://127.0.0.1:54322/"
print("OK: environment port fallback and later override")

with tempfile.TemporaryDirectory() as temp:
    root = Path(temp)
    project = root / "project"
    project.mkdir()
    registry = root / "registry" / "projects"
    registry.mkdir(parents=True)
    (registry / "command.path.json").write_text(json.dumps({"target": str(project)}), encoding="utf-8")
    path = root / "launcher.config.json"
    probe = "import pathlib,sys;sys.exit(0 if pathlib.Path('ready').exists() else 1)"
    path.write_text(json.dumps({"schema_version": 1, "launcher": {}, "services": [{
        "id": "command", "category": "service", "project_ref": "command",
        "display": {"name": "Command health fixture"},
        "lifecycle": {"start": [sys.executable, "-c", "pass"]},
        "health": {"mode": "command", "command": [sys.executable, "-c", probe],
                   "port": 54323, "timeout_seconds": 1},
        "url": "http://127.0.0.1:54323/",
    }]}), encoding="utf-8")
    validation = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate_config.py"), str(path)],
        capture_output=True, text=True,
    )
    assert validation.returncode == 0, validation.stdout + validation.stderr
    launcher.LOG_DIR = root / "logs"
    manager = launcher.ServiceManager(launcher.load_config(path))
    service = manager.services["command"]
    assert not manager._ready(service)
    (project / "ready").write_text("ready\n", encoding="utf-8")
    assert manager._ready(service)
    assert manager.service_port(service) == 54323
print("OK: project-owned command readiness and display-only port")

with tempfile.TemporaryDirectory() as temp:
    root = Path(temp)
    first = root / "first"
    second = root / "second"
    first.mkdir()
    second.mkdir()
    (first / ".env").write_text("WEB_PORT=4100\nAPI_PORT=5100\n", encoding="utf-8")
    (second / ".env").write_text("PORT=5100\n", encoding="utf-8")
    registry = root / "registry" / "projects"
    registry.mkdir(parents=True)
    (registry / "first.path.json").write_text(json.dumps({"target": str(first)}), encoding="utf-8")
    (registry / "second.path.json").write_text(json.dumps({"target": str(second)}), encoding="utf-8")
    path = root / "launcher.config.json"
    path.write_text(json.dumps({"schema_version": 1, "launcher": {}, "services": [
        {"id": "first", "category": "frontend", "project_ref": "first",
         "display": {"name": "First service"},
         "lifecycle": {"start": [sys.executable, "-c", "pass"]},
         "health": {"mode": "env", "port_key": "WEB_PORT"},
         "ports": [
             {"name": "WebUI", "mode": "env", "port_key": "WEB_PORT"},
             {"name": "API", "mode": "env", "port_key": "API_PORT"},
         ]},
        {"id": "second", "category": "backend", "project_ref": "second",
         "display": {"name": "Second service"},
         "lifecycle": {"start": [sys.executable, "-c", "pass"]},
         "health": {"mode": "env", "port_key": "PORT"},
         "ports": [{"name": "API", "mode": "env", "port_key": "PORT"}]},
    ]}), encoding="utf-8")
    launcher.LOG_DIR = root / "logs"
    manager = launcher.ServiceManager(launcher.load_config(path))
    stopped = lambda service_id: {
        "id": service_id, "running": False, "ready": False, "pid": None, "exit_code": None,
        "state": "stopped", "problem": None, "desired": "unknown", "last_change_at": None,
    }
    with mock.patch.object(manager, "status", side_effect=stopped):
        services = {item["id"]: item for item in manager.public_services()}
        assert [item["port"] for item in services["first"]["ports"]] == [4100, 5100]
        assert services["first"]["port_conflicts"] == [{"port": 5100, "with": ["Second service"]}]
        assert services["second"]["port_conflicts"] == [{"port": 5100, "with": ["First service"]}]
        (second / ".env").write_text("PORT=5200\n", encoding="utf-8")
        services = {item["id"]: item for item in manager.public_services()}
        assert not services["first"]["port_conflicts"]
        assert not services["second"]["port_conflicts"]
print("OK: declared multi-port bindings and cross-service conflict detection")

with tempfile.TemporaryDirectory() as temp:
    root = Path(temp)
    project = root / "project"
    project.mkdir()
    registry = root / "registry" / "projects"
    registry.mkdir(parents=True)
    (registry / "api.path.json").write_text(json.dumps({"target": str(project)}), encoding="utf-8")
    path = root / "launcher.config.json"
    path.write_text(json.dumps({"schema_version": 1, "launcher": {}, "services": [{
        "id": "api", "category": "backend", "project_ref": "api",
        "display": {"name": "Synthetic API"},
        "lifecycle": {"start": [sys.executable, "-c", "pass"]},
        "health": {"mode": "http", "url": "http://127.0.0.1:54321/health",
                   "http_probe_interval_seconds": 30}
    }]}), encoding="utf-8")
    launcher.LOG_DIR = root / "logs"
    manager = launcher.ServiceManager(launcher.load_config(path))

    class FakeConnection:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False

    class FakeResponse(FakeConnection):
        status = 200

    with mock.patch.object(launcher.socket, "create_connection", return_value=FakeConnection()) as tcp_probe, \
         mock.patch.object(launcher.urllib.request, "urlopen", return_value=FakeResponse()) as http_probe:
        assert manager.status("api")["ready"]
        assert manager.status("api")["ready"]
        assert tcp_probe.call_count == 2
        assert http_probe.call_count == 1
print("OK: lightweight TCP sampling with cached successful HTTP probe")

with tempfile.TemporaryDirectory() as temp:
    root = Path(temp)
    project = root / "project"
    project.mkdir()
    registry = root / "registry" / "projects"
    registry.mkdir(parents=True)
    (registry / "progress.path.json").write_text(json.dumps({"target": str(project)}), encoding="utf-8")
    path = root / "launcher.config.json"
    path.write_text(json.dumps({"schema_version": 1, "launcher": {}, "services": [{
        "id": "progress", "category": "service", "project_ref": "progress",
        "display": {"name": "Progress fixture"},
        "lifecycle": {
            "start": [sys.executable, "-c", "pass"],
            "update": [sys.executable, "-c", (
                "print('LAUNCHER_PROGRESS {\\\"percent\\\":42,\\\"message\\\":\\\"Downloading\\\"}');"
                "print('\\033[31msynthetic failure\\033[0m');raise SystemExit(7)"
            )],
        },
        "health": {"mode": "tcp", "port": 1},
        "validation": {"action_timeout_seconds": 5},
    }]}), encoding="utf-8")
    launcher.LOG_DIR = root / "logs"
    manager = launcher.ServiceManager(launcher.load_config(path))
    manager._begin_operation("progress", "update", "Preparing")
    try:
        manager._run_finite_action(manager.services["progress"], "update")
        raise AssertionError("failed synthetic update must raise ActionError")
    except launcher.ActionError as exc:
        assert exc.code == "action_failed"
        assert exc.exit_code == 7
        assert exc.detail == "synthetic failure"
    operation = manager.operation("progress")
    assert operation and operation["progress"] == 42 and operation["message"] == "Downloading"
    try:
        manager.start("progress")
        raise AssertionError("concurrent service action must be rejected")
    except launcher.ActionError as exc:
        assert exc.code == "action_in_progress"
    rendered_log = manager.log_tail("progress")
    assert "LAUNCHER_PROGRESS" not in rendered_log
    assert "\x1b" not in rendered_log
    assert "PROGRESS 42% Downloading" in rendered_log
    assert "ACTION update FAILED code=7" in rendered_log
    manager._finish_operation("progress")
    assert not manager.has_active_operations()

    service = manager.services["progress"]
    service["update"] = [sys.executable, "-c", (
        "print('LAUNCHER_PROGRESS {\\\"percent\\\":75,\\\"message\\\":\\\"Almost done\\\"}')"
    )]
    manager._begin_operation("progress", "update", "Preparing")
    try:
        manager._run_finite_action(service, "update")
        raise AssertionError("an update without the 100% marker must fail")
    except launcher.ActionError as exc:
        assert exc.code == "progress_incomplete"
    manager._finish_operation("progress")

    service["update"] = [sys.executable, "-c", (
        "print('LAUNCHER_PROGRESS {\\\"percent\\\":100,\\\"message\\\":\\\"Complete\\\"}')"
    )]
    manager._begin_operation("progress", "update", "Preparing")
    manager._run_finite_action(service, "update")
    manager._finish_operation("progress")
    assert "ACTION update SUCCESS" in manager.log_tail("progress")
print("OK: action progress, readable logs, and per-service concurrency guard")

presence = launcher.ClientPresence(15)
assert presence.active_clients == 0
assert not presence.should_exit()
presence.connected()
presence.last_zero_at -= 30
assert not presence.should_exit()
presence.disconnected()
assert not presence.should_exit()
presence.last_zero_at -= 16
assert presence.should_exit()
presence.connected()
assert not presence.should_exit()
print("OK: WebUI idle exit waits for the last client and cancels on reconnect")


class ShutdownManager:
    def public_services(self):
        return []

    def has_active_operations(self):
        return False


class FakeShutdownServer:
    def __init__(self):
        self.shutdown_called = threading.Event()

    def shutdown(self):
        self.shutdown_called.set()


shutdown_handler_base = launcher.make_handler(
    ShutdownManager(), "synthetic-token", "Synthetic Launcher"
)


class SyntheticShutdownHandler(shutdown_handler_base):
    def __init__(self):
        self.path = "/api/shutdown"
        self.headers = {"X-Launcher-Token": "synthetic-token"}
        self.server = FakeShutdownServer()
        self.response = None

    def _json(self, status, payload):
        self.response = (status, payload)


shutdown_handler = SyntheticShutdownHandler()
shutdown_handler.do_POST()
assert shutdown_handler.response == (202, {"status": "shutting-down"})
assert shutdown_handler.server.shutdown_called.wait(timeout=1)
print("OK: authenticated WebUI shutdown exits the dashboard server")


class BusyShutdownManager(ShutdownManager):
    def has_active_operations(self):
        return True


busy_shutdown_handler_base = launcher.make_handler(
    BusyShutdownManager(), "synthetic-token", "Synthetic Launcher"
)


class BusyShutdownHandler(busy_shutdown_handler_base):
    def __init__(self):
        self.path = "/api/shutdown"
        self.headers = {"X-Launcher-Token": "synthetic-token"}
        self.server = FakeShutdownServer()
        self.response = None

    def _json(self, status, payload):
        self.response = (status, payload)


busy_shutdown_handler = BusyShutdownHandler()
busy_shutdown_handler.do_POST()
assert busy_shutdown_handler.response[0] == 409
assert busy_shutdown_handler.response[1]["error"] == "action_in_progress"
assert not busy_shutdown_handler.server.shutdown_called.is_set()
print("OK: dashboard shutdown is rejected during an active operation")


class FakeManager:
    def __init__(self):
        self.services = {"probe": {"id": "probe", "health": {"port": 1}, "validation": {
            "startup_timeout_seconds": 0.1, "stability_seconds": 0,
            "shutdown_timeout_seconds": 0.1, "poll_interval_seconds": 0.01,
        }}}
        self.started_by_launcher = set()
        self.active = False
        self.actions = []

    def status(self, service_id):
        problem = "stopped-unexpectedly" if self.started_by_launcher and not self.active else None
        return {"id": service_id, "running": self.active, "ready": self.active,
                "pid": 123 if self.active else None, "exit_code": None,
                "state": "ready" if self.active else "stopped-unexpectedly" if problem else "stopped",
                "problem": problem}

    def start(self, service_id):
        self.actions.append("start")
        self.active = True
        self.started_by_launcher.add(service_id)
        return self.status(service_id)

    def stop(self, service_id):
        self.actions.append("stop")
        self.active = False
        self.started_by_launcher.discard(service_id)
        return self.status(service_id)

    def restart(self, service_id):
        self.actions.append("restart")
        self.active = True
        self.started_by_launcher.add(service_id)
        return self.status(service_id)

    def interrupt_for_validation(self, service_id):
        self.actions.append("interrupt")
        self.active = False


fake = FakeManager()
result = verify.verify_service(fake, "probe")
assert result["passed"]
assert fake.actions == ["start", "stop", "start", "interrupt", "start", "restart", "stop"]
assert fake.active is False
print("OK: mandatory lifecycle verification sequence")
