# Agent contract

This checkout is the Dashboard application. Do not generate, copy, or maintain a second Dashboard project beside it. Read `SKILL.md` before configuring a real service.

## Ownership boundary

- Tracked source: `dashboard/`, `scripts/`, `defaults/`, `references/`, `recipes/`, `examples/`, `SKILL.md`, and project documentation.
- Private instance state: the resolved local workspace, `.local-dashboard/` by default or `LOCAL_SERVICE_DASHBOARD_DATA_DIR` when explicitly set.
- External projects: only paths explicitly supplied by the user and registered through `dashboard/project_registry.py`.
- Never scan parent, sibling, home, common project, port, or process locations to discover services.

Real registrations, service descriptors, adapters, entrypoints, environment values, logs, reports, caches, observed revisions, and machine paths belong only in the ignored workspace. Tracked examples must remain synthetic. Do not customize a tracked recipe in place.

## Cold start

1. Run `python3 scripts/init_dashboard.py --dry-run`, then `python3 scripts/init_dashboard.py`.
2. The initializer must create only the private workspace. It must not copy runtime source.
3. Register each explicit path with `python3 dashboard/project_registry.py <project-ref> <path> [--visible-name name]`.
4. Edit the reported workspace `launcher.config.json`, using only registered `project_ref` values and the schema in `references/configuration.md`.
5. Put unavoidable instance glue in workspace `adapters/<service-id>/` and reference the supplied `PROJECT_ROOT`; never embed a project path.

## Lifecycle and repository rules

- Health, Open URL, declared ports, lifecycle update, and Git upstream status are separate contracts.
- Git status checks are informational and non-mutating. They must never fetch, pull, checkout, merge, or enable an Update button by themselves.
- Use a project-owned safe updater only when one exists. Updates need progress records, single-flight locking, validation, and atomic replacement.
- Never stop or kill an unidentified process. Restart is verified stop then start.
- Bind the Dashboard to loopback and preserve the per-session API token.

## Required verification

Run before committing or pushing:

```text
python3 scripts/smoke_test.py
python3 scripts/audit_privacy.py
python3 -m py_compile dashboard/*.py scripts/*.py
node --check dashboard/ui/app.js
```

Also run lifecycle verification in an approved test window for every real service and available target OS. Preserve the old instance after migration until the user explicitly approves archival. Git must remain clean after normal workspace use; framework edits must remain visible.
