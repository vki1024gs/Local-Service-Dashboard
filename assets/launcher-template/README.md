# Local Service Dashboard

This private instance displays and manually controls explicitly registered local services. It listens only on localhost, does not scan for projects, does not reserve application ports, and does not automatically restart services.

## Before launch

1. Register each explicitly supplied project with `dashboard/register_project.py`.
2. Replace the synthetic service in `dashboard/launcher.config.json`.
3. Validate the configuration with the linked framework's validator and `python dashboard/launcher.py --check-config`.
4. Run complete lifecycle verification when it is safe to start and stop the service.

Update-capable services show live progress on their card. While an update is active, conflicting controls and dashboard exit are disabled. Failures open a readable explanation with a direct link to cleaned action logs.

## Launch

- macOS: double-click `launch-dashboard.command`.
- Windows: double-click `launch-dashboard.vbs` for a console-free launch. The `.bat` entrypoint remains as a compatibility fallback and immediately delegates to it.

## Layout

- `dashboard/`: configuration, registry, runtime, UI, logs, and validation report.
- `projects/`: shortcuts to registered projects.
- `launcher-skill`: link or path pointer to the reusable framework source.
- `ARCHITECTURE.md`: structure and runtime boundaries.
- `AGENTS.md`: maintenance rules for a new agent.

The dashboard may exit after its last WebUI client closes. Business services continue running by default.
