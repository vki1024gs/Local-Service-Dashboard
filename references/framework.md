# Framework contract

The clone is the Dashboard application. `dashboard/` is the single tracked runtime source. `scripts/init_dashboard.py` creates only the ignored workspace; no supported workflow creates a second Dashboard.

```text
repository/                         workspace (ignored)
├─ dashboard/ runtime + UI          ├─ workspace.json
├─ scripts/ tools                   ├─ launcher.config.json
├─ examples/ recipes/ references/   ├─ registry/projects/
├─ launch-dashboard.vbs             ├─ projects/ links or pointers
└─ SKILL.md                         ├─ adapters/ entrypoints/
                                    └─ logs/ reports/ cache/ backups/ imports/
```

## Registration

Initialize and register only explicit paths:

```text
python3 scripts/init_dashboard.py
python3 dashboard/project_registry.py <project-ref> <explicit-project-path> --visible-name <english-name>
```

The registrar writes a versioned private record and a symlink, Windows junction, or pointer fallback. It never copies a project. Service descriptors store only `project_ref`. Optional Git URL/branch metadata remains private and must not contain credentials.

## Fixed categories

Use only `static-web`, `frontend`, `backend`, or `service`. Lifecycle commands run in the registered project root. The runtime supplies `PROJECT_ROOT` and `DASHBOARD_WORKSPACE_ROOT`.

## Source of truth

1. Project-owned scripts, manifests, env files, and health endpoints are authoritative.
2. Health, Open URL, declared ports, lifecycle update, and Git upstream status are separate contracts.
3. Prefer dynamic manifest/env bindings over copied names and port numbers.
4. Prefer application-level HTTP or project-owned command readiness; TCP is valid only when the socket is the readiness contract.
5. Use a workspace adapter only when no project-owned command can satisfy the lifecycle contract.
6. Never scan arbitrary ports or processes, auto-restart, reserve business ports, or kill an unidentified listener.

## Action safety

Only one lifecycle action may affect a service at a time. Restart is verified stop then start. A safe updater uses a cross-process lock, unique temporary output, validation, atomic replacement, and monotonic `LAUNCHER_PROGRESS` records. Dashboard exit is rejected while an action runs.

Repository checks are background, cached, bounded, and non-mutating. They may compare `ls-remote` with already-known local commits; they never fetch, pull, merge, checkout, or update refs.

Repository checks are startup-only by default and may be explicitly refreshed from the WebUI. Positive configured intervals opt into periodic checking. On Windows, `launch-dashboard.vbs` is the console-free entrypoint and Dashboard-owned subprocesses use hidden creation flags while retaining captured diagnostics.

## Drift test

When configuration binds to a project manifest or env port, change that synthetic source during an approved test and confirm the Dashboard follows it without tracked edits. Restore the fixture afterward.
