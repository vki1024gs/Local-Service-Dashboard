# Framework contract

Use the bundled framework as-is. Do not ask the Agent to invent a launcher layout, field names, path variables, or lifecycle conventions.

## Fixed layout

```text
launcher/
├── AGENTS.md                    # concise Agent operating rules
├── ARCHITECTURE.md              # structure, boundaries, and data flow
├── README.md                    # user-facing launch instructions
├── launch-dashboard.command     # macOS user entrypoint
├── launch-dashboard.bat         # Windows user entrypoint
├── launcher-skill -> ...        # link/pointer to the installed reusable Skill
├── projects/                    # links to explicitly registered projects
└── dashboard/                   # organized implementation directory
    ├── .launcher-instance      # exists only in a materialized private instance
    ├── launcher.py             # shared runtime; do not fork per service
    ├── launcher.config.json    # schema v1 descriptors only
    ├── register_project.py     # project registration helper
    ├── registry/projects/      # symlink, junction, or .path.json fallback
    ├── adapters/               # exceptional thin adapters only
    ├── entrypoints/            # optional instance-local GUI launch wrappers
    ├── ui/                     # shared real-time dashboard
    └── logs/                   # runtime-created logs and reports
```

## Fixed categories

| Category | Intended target | Lifecycle rule |
|---|---|---|
| `static-web` | Static HTML/site directory | Prefer an existing serve script; use the built-in Python server only when no project script exists. |
| `frontend` | Browser development server | Call the project-owned package script, such as `npm run dev`; do not reproduce its command line. |
| `backend` | API or application backend | Call the project-owned entry script or task runner. |
| `service` | Custom/background service | Require a project-owned finite `stop` command when start detaches. |

Do not create new category names. Do not add unknown configuration fields.

## Project registration

First materialize the framework from the Skill root:

```bash
python scripts/create_launcher.py <explicit-destination>
```

Never register a project in `assets/launcher-template/`. The template lacks `dashboard/.launcher-instance`, so both registration and normal execution refuse to run there.

Then run this from the generated launcher directory:

```bash
python dashboard/register_project.py <project-ref> <explicit-project-path> --visible-name "<english-name>" --replace
```

Keep every directory and file name in English. Use lowercase kebab-case for project shortcuts and supporting directories; retain conventional uppercase names only for `README.md`, `ARCHITECTURE.md`, and `AGENTS.md`. `projects` contains links to original projects; `dashboard` contains configuration, registration, logs, reports, adapters, runtime, and UI assets; `launcher-skill` makes the installed Skill discoverable without copying it. Do not scatter implementation files or runtime state across the root.

The registrar tries a relative directory symlink first. On Windows it falls back to a directory junction, then to `<project-ref>.path.json` if links are unavailable. It never copies or hard-links the project. The service descriptor stores only `project_ref`; never store the original absolute project path in `launcher.config.json`.

Optional GUI launch wrappers belong under `dashboard/entrypoints/`, not under service `adapters/`. They must locate the instance relative to their own bundle or executable and must not embed registered project paths. Keep the fixed English `.command` and `.bat` launch files as portable fallback entrypoints.

## Action safety

Only one lifecycle action may affect a service at a time. While an update is active, the runtime exposes its current operation through the live service snapshot, rejects competing start/stop/restart/update requests, prevents idle exit, and rejects explicit dashboard shutdown. The WebUI must preserve this busy state across live samples instead of merely disabling the clicked DOM element.

Project-owned update scripts provide the second safety layer. They must reject concurrent invocations across launcher-process restarts, use a unique temporary download, validate before replacement, and install through an atomic same-filesystem rename. A project start script must refuse to launch while that update lock is active. A stale lock must be detected deliberately; never treat a fixed shared temporary filename as a lock.

## Source-of-truth rules

1. Treat project-owned lifecycle scripts and manifests as authoritative.
2. Run lifecycle commands with the registered project as `cwd`; keep commands relative, such as `["npm", "run", "dev"]` or `["./start.command"]`.
3. Supply the resolved target as `PROJECT_ROOT` automatically. Never duplicate its absolute value in commands or adapters.
4. Prefer `health.mode=env` when the project owns its port in `.env`; the dashboard rereads it while monitoring. When socket acceptance is weaker than real application readiness, use an application-level HTTP endpoint or a project-owned, read-only `health.mode=command` probe.
5. Prefer `display.name_from` when a JSON manifest owns the project name; the dashboard rereads it while monitoring.
6. Use `health.mode=auto` only when the project reliably prints its localhost URL. Use fixed HTTP/TCP health only when no project-owned dynamic source exists.
7. If an adapter is unavoidable, place it under `dashboard/adapters/<service-id>/`, make it call the project through `PROJECT_ROOT`, and keep project constants out of it.

## Drift test

After configuration, change the test project's manifest name or `.env` port during an approved test. Confirm the dashboard follows the new value without editing launcher code or lifecycle commands. Restore the test project afterward.
