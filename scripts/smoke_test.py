#!/usr/bin/env python3
import importlib.util
import json
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from unittest import mock

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "dashboard" / "launcher.py"
INITIALIZE = ROOT / "scripts" / "init_dashboard.py"
REGISTER_PROJECT = ROOT / "dashboard" / "register_project.py"
BUNDLE = ROOT / "scripts" / "config_bundle.py"
VALIDATE_CONFIG = ROOT / "scripts" / "validate_config.py"
assert LAUNCHER.is_file()
assert not any(any(ord(character) > 127 for character in path.name) for path in ROOT.rglob("*")
               if ".git" not in path.parts and ".local-dashboard" not in path.parts)
sys.path.insert(0, str(ROOT / "dashboard"))

import project_registry
import repository_status
import workspace as workspace_module


def register_fixture(root: Path, project_ref: str, target: Path) -> None:
    registry = root / "registry" / "projects"
    registry.mkdir(parents=True, exist_ok=True)
    (registry / f"{project_ref}.json").write_text(json.dumps({
        "schemaVersion": 1,
        "documentType": "registered-project",
        "projectRef": project_ref,
        "visibleName": project_ref.replace("_", "-"),
        "target": str(target.resolve()),
    }), encoding="utf-8")

with tempfile.TemporaryDirectory() as temp:
    destination = Path(temp) / "workspace"
    subprocess.run([sys.executable, str(INITIALIZE), "--data-dir", str(destination)], check=True,
                   capture_output=True, text=True)
    assert (destination / "workspace.json").is_file()
    assert (destination / "projects").is_dir()
    assert (destination / "launcher.config.json").is_file()
    assert not (destination / "dashboard").exists()
    repeated = subprocess.run([sys.executable, str(INITIALIZE), "--data-dir", str(destination)],
                              check=True, capture_output=True, text=True)
    assert "ALREADY_INITIALIZED" in repeated.stdout
    incompatible = Path(temp) / "incompatible"
    incompatible.mkdir()
    (incompatible / "workspace.json").write_text(json.dumps({
        "schemaVersion": 999,
        "documentType": "local-service-dashboard-workspace",
        "applicationId": "local-service-dashboard",
    }), encoding="utf-8")
    refused = subprocess.run([sys.executable, str(INITIALIZE), "--data-dir", str(incompatible)],
                             capture_output=True, text=True)
    assert refused.returncode != 0 and "incompatible" in refused.stderr.lower()
print("OK: in-place Dashboard initialization creates private state only")

with tempfile.TemporaryDirectory() as temp:
    config = Path(temp) / "launcher.config.json"
    config.write_text(json.dumps({
        "schema_version": 1,
        "launcher": {"host": "127.0.0.1", "repository_check_interval_seconds": 0},
        "services": [],
    }), encoding="utf-8")
    validated = subprocess.run(
        [sys.executable, str(VALIDATE_CONFIG), str(config)], capture_output=True, text=True
    )
    assert validated.returncode == 0, validated.stdout + validated.stderr
    document = json.loads(config.read_text(encoding="utf-8"))
    document["launcher"]["repository_check_interval_seconds"] = False
    config.write_text(json.dumps(document), encoding="utf-8")
    rejected = subprocess.run(
        [sys.executable, str(VALIDATE_CONFIG), str(config)], capture_output=True, text=True
    )
    assert rejected.returncode != 0
print("OK: zero repository interval is valid for startup-only checks")

before_status = subprocess.run(["git", "status", "--short"], cwd=ROOT, check=True,
                               capture_output=True, text=True).stdout
subprocess.run([sys.executable, str(INITIALIZE)], cwd=ROOT, check=True,
               capture_output=True, text=True)
after_status = subprocess.run(["git", "status", "--short"], cwd=ROOT, check=True,
                              capture_output=True, text=True).stdout
assert before_status == after_status
subprocess.run(["git", "check-ignore", "-q", ".local-dashboard/workspace.json"],
               cwd=ROOT, check=True)
print("OK: default local workspace use leaves Git status unchanged")

with tempfile.TemporaryDirectory() as temp:
    root = Path(temp)
    workspace_root = root / "workspace"
    subprocess.run(
        [sys.executable, str(INITIALIZE), "--data-dir", str(workspace_root)],
        check=True,
        capture_output=True,
        text=True,
    )
    workspace = workspace_module.require_workspace(workspace_root)
    remote = root / "remote.git"
    project = root / "project"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
    subprocess.run(["git", "init", "-b", "main", str(project)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(project), "config", "user.name", "Synthetic Test"], check=True)
    subprocess.run(["git", "-C", str(project), "config", "user.email", "test@example.invalid"], check=True)
    (project / "version.txt").write_text("one\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(project), "add", "version.txt"], check=True)
    subprocess.run(["git", "-C", str(project), "commit", "-m", "initial"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(project), "remote", "add", "origin", str(remote)], check=True)
    subprocess.run(["git", "-C", str(project), "push", "-u", "origin", "main"], check=True, capture_output=True)
    record, _ = project_registry.register_project(
        "synthetic-project", project, workspace=workspace
    )
    assert record["repository"]["url"] == str(remote)
    assert project_registry.resolve_project_ref("synthetic-project", workspace) == project.resolve()
    try:
        project_registry.register_project(
            "shortcut-collision", project, visible_name="synthetic-project",
            detect_git=False, workspace=workspace,
        )
        raise AssertionError("shortcut collision must fail")
    except ValueError:
        assert not (workspace.registry / "shortcut-collision.json").exists()
    try:
        project_registry.register_project(
            "credential-url", project, repository_url="https://user:secret@example.invalid/repo.git",
            branch="main", workspace=workspace,
        )
        raise AssertionError("credential-bearing repository URL must fail")
    except ValueError:
        assert not (workspace.registry / "credential-url.json").exists()
    current = repository_status.inspect_repository(project, record["repository"])
    assert current["state"] == "current", current
    second = root / "second"
    subprocess.run(["git", "clone", "-b", "main", str(remote), str(second)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(second), "config", "user.name", "Synthetic Test"], check=True)
    subprocess.run(["git", "-C", str(second), "config", "user.email", "test@example.invalid"], check=True)
    (second / "version.txt").write_text("two\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(second), "commit", "-am", "new version"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(second), "push", "origin", "main"], check=True, capture_output=True)
    different = repository_status.inspect_repository(project, record["repository"])
    assert different["state"] == "unknown_relation", different
    subprocess.run(["git", "-C", str(project), "fetch", "origin", "main"], check=True, capture_output=True)
    ref_before = subprocess.run(["git", "-C", str(project), "show-ref"], check=True,
                                capture_output=True, text=True).stdout
    status_before = subprocess.run(["git", "-C", str(project), "status", "--porcelain"], check=True,
                                   capture_output=True, text=True).stdout
    update = repository_status.inspect_repository(project, record["repository"])
    assert update["state"] == "update_available", update
    assert subprocess.run(["git", "-C", str(project), "show-ref"], check=True,
                          capture_output=True, text=True).stdout == ref_before
    assert subprocess.run(["git", "-C", str(project), "status", "--porcelain"], check=True,
                          capture_output=True, text=True).stdout == status_before
    subprocess.run(["git", "-C", str(project), "merge", "--ff-only", "origin/main"],
                   check=True, capture_output=True)
    (project / "local.txt").write_text("local\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(project), "add", "local.txt"], check=True)
    subprocess.run(["git", "-C", str(project), "commit", "-m", "local change"],
                   check=True, capture_output=True)
    ahead = repository_status.inspect_repository(project, record["repository"])
    assert ahead["state"] == "ahead", ahead
    (second / "remote.txt").write_text("remote\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(second), "add", "remote.txt"], check=True)
    subprocess.run(["git", "-C", str(second), "commit", "-m", "remote change"],
                   check=True, capture_output=True)
    subprocess.run(["git", "-C", str(second), "push", "origin", "main"],
                   check=True, capture_output=True)
    subprocess.run(["git", "-C", str(project), "fetch", "origin", "main"],
                   check=True, capture_output=True)
    diverged = repository_status.inspect_repository(project, record["repository"])
    assert diverged["state"] == "diverged", diverged
print("OK: private registration and non-mutating Git version status")

monitor = repository_status.RepositoryStatusMonitor(interval_seconds=30)
release_check = threading.Event()
check_finished = threading.Event()
calls = []

def synthetic_repository_check(target, repository):
    calls.append((target, repository))
    release_check.wait(timeout=2)
    check_finished.set()
    return {"state": "current", "checked_at": 1e20}

with mock.patch.object(repository_status, "inspect_repository", side_effect=synthetic_repository_check):
    metadata = {"url": "https://example.invalid/repository.git", "branch": "main", "remote": "origin"}
    assert monitor.status("single-flight", ROOT, metadata)["state"] == "checking"
    assert monitor.status("single-flight", ROOT, metadata)["state"] == "checking"
    release_check.set()
    assert check_finished.wait(timeout=2)
    for _ in range(100):
        observed = monitor.status("single-flight", ROOT, metadata)
        if observed["state"] == "current":
            break
        threading.Event().wait(0.01)
    assert observed["state"] == "current" and len(calls) == 1
print("OK: repository status monitor is cached and single-flight")

startup_only_monitor = repository_status.RepositoryStatusMonitor(interval_seconds=0)
startup_check_finished = threading.Event()
startup_calls = []

def synthetic_startup_check(target, repository):
    startup_calls.append((target, repository))
    startup_check_finished.set()
    return {"state": "current", "checked_at": 1}

with mock.patch.object(repository_status, "inspect_repository", side_effect=synthetic_startup_check):
    metadata = {"url": "https://example.invalid/repository.git", "branch": "main", "remote": "origin"}
    assert startup_only_monitor.status("startup-only", ROOT, metadata)["state"] == "checking"
    assert startup_check_finished.wait(timeout=2)
    for _ in range(100):
        observed = startup_only_monitor.status("startup-only", ROOT, metadata)
        if observed["state"] == "current":
            break
        threading.Event().wait(0.01)
    for _ in range(10):
        startup_only_monitor.status("startup-only", ROOT, metadata)
        threading.Event().wait(0.01)
    assert observed["state"] == "current" and len(startup_calls) == 1
print("OK: zero repository interval checks once at startup only")

if sys.platform == "win32":
    completed = subprocess.CompletedProcess(["git"], 0, stdout="", stderr="")
    with mock.patch.object(repository_status.subprocess, "run", return_value=completed) as run_git:
        repository_status._run_git(ROOT, ["status"])
    assert run_git.call_args.kwargs["creationflags"] & subprocess.CREATE_NO_WINDOW

    revision = "a" * 40
    results = [
        subprocess.CompletedProcess(["git"], 0, stdout=f"{revision}\n", stderr=""),
        subprocess.CompletedProcess(["git"], 0, stdout="main\n", stderr=""),
        subprocess.CompletedProcess(["git"], 0, stdout="", stderr=""),
        subprocess.CompletedProcess(["git"], 0, stdout=f"{revision}\trefs/heads/main\n", stderr=""),
    ]
    with mock.patch.object(repository_status.subprocess, "run", side_effect=results) as all_git:
        repository_status.inspect_repository(
            ROOT, {"url": "https://example.invalid/repository.git", "branch": "main", "remote": "origin"}
        )
    assert len(all_git.call_args_list) == 4
    assert all(
        call.kwargs["creationflags"] & subprocess.CREATE_NO_WINDOW
        for call in all_git.call_args_list
    )
    print("OK: repository Git checks hide their Windows console")

with tempfile.TemporaryDirectory() as temp:
    root = Path(temp)
    project = root / "portable-project"
    project.mkdir()
    source = root / "source-workspace"
    target = root / "target-workspace"
    for workspace_root in (source, target):
        subprocess.run([sys.executable, str(INITIALIZE), "--data-dir", str(workspace_root)],
                       check=True, capture_output=True, text=True)
    source_workspace = workspace_module.require_workspace(source)
    project_registry.register_project("portable-project", project, detect_git=False,
                                      workspace=source_workspace)
    source_workspace.config.write_text(json.dumps({
        "schema_version": 1,
        "launcher": {"host": "127.0.0.1"},
        "services": [{
            "id": "portable-project", "category": "service",
            "project_ref": "portable-project", "display": {"name": "Portable fixture"},
            "lifecycle": {"start": [sys.executable, "-c", "pass"]},
            "health": {"mode": "tcp", "port": 54329},
            "env": {"SYNTHETIC_TOKEN": "must-not-export"},
        }],
    }), encoding="utf-8")
    adapter = source_workspace.adapters / "portable" / "start.py"
    adapter.parent.mkdir(parents=True)
    adapter.write_text("import os\nassert os.environ['PROJECT_ROOT']\n", encoding="utf-8")
    bundle = root / "portable-bundle.json"
    subprocess.run([
        sys.executable, str(BUNDLE), "--data-dir", str(source), "export", str(bundle),
        "--adapter", "portable/start.py",
    ], check=True, capture_output=True, text=True)
    exported = bundle.read_text(encoding="utf-8")
    assert str(project) not in exported and "must-not-export" not in exported
    mapping = f"portable-project={project}"
    preview = subprocess.run([
        sys.executable, str(BUNDLE), "--data-dir", str(target), "import", str(bundle),
        "--map", mapping,
    ], check=True, capture_output=True, text=True)
    assert "PREVIEW complete" in preview.stdout
    subprocess.run([
        sys.executable, str(BUNDLE), "--data-dir", str(target), "import", str(bundle),
        "--map", mapping, "--apply",
    ], check=True, capture_output=True, text=True)
    imported = json.loads((target / "launcher.config.json").read_text(encoding="utf-8"))
    assert "env" not in imported["services"][0]
    assert (target / "adapters" / "portable" / "start.py").is_file()
print("OK: sanitized configuration bundle preview and round-trip")

for guide in (ROOT / "README.md", ROOT / "AGENTS.md", ROOT / "SKILL.md"):
    text = guide.read_text(encoding="utf-8")
    assert "create_launcher.py <" not in text
    assert "assets/launcher-template" not in text
assert "never create a second dashboard" in (
    ROOT / "agents" / "openai.yaml"
).read_text(encoding="utf-8").lower()
print("OK: repository-resident Agent guidance uses one in-place Dashboard")
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
    register_fixture(root, "probe", project)
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
    assert manager.services["probe"]["cwd"] == str(project.resolve())
    assert manager.services["probe"]["env"]["PROJECT_ROOT"] == str(project.resolve())
    assert manager.start("probe")["running"]
    assert manager.stop("probe")["running"] is False
print("OK: launcher process lifecycle")

with tempfile.TemporaryDirectory() as temp:
    root = Path(temp)
    project = root / "project"
    project.mkdir()
    (project / "package.json").write_text(
        '{"name":"alpha-ui","version":"1.2.3"}', encoding="utf-8"
    )
    (project / ".env").write_text("PORT=3100\n", encoding="utf-8")
    register_fixture(root, "web", project)
    path = root / "launcher.config.json"
    path.write_text(json.dumps({"schema_version": 1, "launcher": {}, "services": [{
        "id": "web", "category": "frontend", "project_ref": "web",
        "display": {
            "name": "fallback",
            "name_from": {"file": "package.json", "json_path": "name"},
            "version_from": {"file": "package.json", "key_path": "version", "prefix": "v"},
        },
        "lifecycle": {"start": [sys.executable, "-c", "pass"]},
        "health": {"mode": "env", "env_file": ".env", "port_key": "PORT", "scheme": "http"},
        "url": "auto"
    }]}), encoding="utf-8")
    launcher.LOG_DIR = root / "logs"
    manager = launcher.ServiceManager(launcher.load_config(path))
    service = manager.services["web"]
    assert manager._display_name(service) == "alpha-ui"
    assert manager._display_version(service) == "v1.2.3"
    assert manager.service_url(service) == "http://127.0.0.1:3100/"
    (project / "package.json").write_text(
        '{"name":"beta-ui","version":"2.0.0-beta.1"}', encoding="utf-8"
    )
    (project / ".env").write_text("PORT=4200\n", encoding="utf-8")
    assert manager._display_name(service) == "beta-ui"
    assert manager._display_version(service) == "v2.0.0-beta.1"
    assert manager.service_url(service) == "http://127.0.0.1:4200/"
    (project / "pyproject.toml").write_text(
        '[project]\nname = "beta-ui"\nversion = "2.1.0"\n', encoding="utf-8"
    )
    service["display"]["version_from"] = {
        "file": "pyproject.toml", "key_path": "project.version", "prefix": "v"
    }
    assert manager._display_version(service) == "v2.1.0"
print("OK: project-owned name and port drift")

with tempfile.TemporaryDirectory() as temp:
    root = Path(temp)
    project = root / "project"
    project.mkdir()
    (project / ".env").write_text("# PORT intentionally omitted\n", encoding="utf-8")
    register_fixture(root, "web", project)
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
    register_fixture(root, "command", project)
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
    register_fixture(root, "first", first)
    register_fixture(root, "second", second)
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
    register_fixture(root, "api", project)
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
    register_fixture(root, "progress", project)
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
