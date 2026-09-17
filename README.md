# Local Service Dashboard

A localhost-only Web dashboard for viewing and manually controlling explicitly registered local services on macOS and Windows. It does not discover projects, reserve application ports, or automatically restart services.

This repository is the reusable framework. A deployed dashboard is generated into a separate private directory so that project paths, commands, ports, logs, and validation reports never enter the framework repository.

## Requirements

- Python 3.10 or newer
- Git
- A browser
- macOS or Windows
- Existing start, stop, and update commands for each service you choose to register

The dashboard itself uses only the Python standard library. Node.js is not required by the dashboard, but an individual registered service may require it.

## Clone and deploy

Clone the repository, then generate a private dashboard instance outside the clone:

```bash
git clone https://github.com/vki1024gs/Local-Service-Dashboard.git
cd Local-Service-Dashboard
python3 scripts/create_launcher.py ../my-local-dashboard
```

On Windows PowerShell:

```powershell
git clone https://github.com/vki1024gs/Local-Service-Dashboard.git
Set-Location Local-Service-Dashboard
py scripts/create_launcher.py ..\my-local-dashboard
```

The destination must not already exist. The generator deliberately keeps the reusable clone separate from machine-specific data.

## Register a project

Register only projects whose paths you already know. The visible name must use lowercase English kebab-case:

```bash
python3 ../my-local-dashboard/dashboard/register_project.py \
  example-app /absolute/path/to/example-app \
  --visible-name example-app
```

Windows example:

```powershell
py ..\my-local-dashboard\dashboard\register_project.py `
  example-app C:\path\to\example-app `
  --visible-name example-app
```

Registration creates a private symlink, junction, or path pointer inside the generated instance. It does not copy the project.

## Configure the service

Edit `my-local-dashboard/dashboard/launcher.config.json`. Start from the bundled synthetic entry and replace it with the registered service. Keep commands relative to the registered project root.

```json
{
  "schema_version": 1,
  "launcher": {
    "title": "My Local Services",
    "host": "127.0.0.1",
    "port": 17321,
    "monitor_interval_seconds": 1,
    "stop_services_on_exit": false
  },
  "services": [
    {
      "id": "example-app",
      "category": "service",
      "project_ref": "example-app",
      "display": {
        "name": "Example App"
      },
      "lifecycle": {
        "start": {
          "macos": ["python3", "-m", "http.server", "8080"],
          "windows": ["py", "-m", "http.server", "8080"]
        }
      },
      "health": {
        "mode": "http",
        "url": "http://127.0.0.1:8080/"
      },
      "url": "http://127.0.0.1:8080/"
    }
  ]
}
```

Only add `lifecycle.update` when the project already has a known safe update procedure. The dashboard runs configured commands, so treat this file as executable local configuration. Never store secrets in it.

Choose a health probe that represents usable service behavior. A listening TCP port is insufficient when an internal runtime can fail after the socket opens; use application-level HTTP or a project-owned, read-only `health.mode: "command"` probe in that case.

For services with multiple endpoints, declare `ports` so the dashboard can show every documented port and flag duplicate declarations. See [Configuration reference](references/configuration.md) and [JSON schema](references/configuration.schema.json).

## Validate before launch

Run validation from the cloned framework directory:

```bash
python3 scripts/validate_config.py ../my-local-dashboard/dashboard/launcher.config.json
python3 ../my-local-dashboard/dashboard/launcher.py --check-config
```

Run a complete lifecycle test only when the service is stopped and it is safe to start and stop it:

```bash
python3 scripts/verify_lifecycle.py ../my-local-dashboard
```

The lifecycle gate checks start, readiness, stability, stop, second start, interruption detection, recovery, restart, and cleanup. It leaves the tested service stopped. Read [Verification](references/verification.md) before using it.

## Start the dashboard

- macOS: double-click `my-local-dashboard/launch-dashboard.command`.
- Windows: double-click `my-local-dashboard/launch-dashboard.vbs` for a console-free launch. The `.bat` entrypoint remains as a compatibility fallback and immediately delegates to it.
- Terminal: run `python3 my-local-dashboard/dashboard/launcher.py`.

The dashboard binds to `127.0.0.1` and uses a per-session API token. The Open action is disabled until its service is ready. Closing the dashboard does not stop business services unless `stop_services_on_exit` was explicitly enabled.
On Windows, lifecycle commands run without opening a console window; their output remains available in the dashboard logs.

## Update

Update the reusable clone and run its tests:

```bash
cd Local-Service-Dashboard
git pull --ff-only
python3 scripts/smoke_test.py
python3 scripts/audit_privacy.py
```

Existing generated instances are intentionally independent copies. Do not overwrite their `dashboard/launcher.config.json`, registry, adapters, logs, or validation report. To adopt a framework update safely, generate a new instance, re-register the same explicit projects, copy only reviewed service descriptors, validate it, and switch after lifecycle verification passes.

Service-level updates are separate: when a service has a configured `lifecycle.update`, its Update action runs that project-owned command and then rechecks health. An update command should not be invented or assumed safe.

Update scripts must stream card progress with `LAUNCHER_PROGRESS` as documented in [Configuration reference](references/configuration.md). A conforming updater must report 100 only after post-install verification, use a cross-process single-flight lock, unique temporary output, validation before replacement, and an atomic rename. A zero exit without the terminal 100 marker is treated as failure. While an update is active, the dashboard rejects conflicting service actions and shutdown. Failures open a readable application dialog with the meaningful error and cleaned log entry instead of a browser alert.

## Troubleshooting

- **The template refuses to run:** expected. Run `scripts/create_launcher.py` and launch the generated instance.
- **Configuration validation fails:** check registration, command nesting, health settings, and unknown fields.
- **A port conflict is shown:** two configured services declare the same port. This is a configuration risk, not proof that an unknown process owns the socket.
- **Open is unavailable:** the readiness probe is not passing, so the destination is intentionally disabled.
- **The service has no PID:** externally started services may not have a launcher-owned PID. Readiness remains authoritative.
- **The dashboard exits after the last tab closes:** this is controlled by its client-idle behavior; business services continue by default.

## Repository checks

```bash
python3 scripts/smoke_test.py
python3 scripts/audit_privacy.py
python3 scripts/validate_config.py assets/launcher-template/dashboard/launcher.config.json
node --check assets/launcher-template/dashboard/ui/app.js  # optional
```

## Security and privacy

The framework stores no real project registrations. Generated instances are private machine configuration and should not be committed. Review [Security policy](SECURITY.md), [Privacy boundary](references/privacy.md), and [Architecture](ARCHITECTURE.md).

## License

MIT. See [LICENSE](LICENSE).
