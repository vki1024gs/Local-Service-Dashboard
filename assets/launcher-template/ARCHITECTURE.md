# Architecture

## Directory contract

```text
launcher/
├── AGENTS.md
├── ARCHITECTURE.md
├── README.md
├── launch-dashboard.command
├── launch-dashboard.bat
├── launch-dashboard.vbs
├── launcher-skill -> <installed-skill>
├── projects/
└── dashboard/
    ├── .launcher-instance
    ├── launcher.py
    ├── launcher.config.json
    ├── register_project.py
    ├── registry/projects/
    ├── adapters/
    ├── entrypoints/
    ├── ui/
    ├── logs/
    └── validation-report.json
```

All path names are English. Root files are entrypoints and documentation; implementation and runtime state stay inside `dashboard`, while project shortcuts stay inside `projects`. On Windows, the VBScript entrypoint starts the dashboard without a console window and the batch entrypoint delegates to it.

## Boundaries

`dashboard/launcher.config.json` is the instance source of truth. Registered project paths live only under `dashboard/registry/projects`. The reusable framework is discoverable through `launcher-skill` and must never receive instance-specific project data.

`health` determines readiness, `url` determines the primary Open destination, and `ports` declares visible endpoints for cross-service conflict checks. The runtime observes only configured services and never scans or reserves arbitrary machine ports.
