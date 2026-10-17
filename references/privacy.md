# Privacy isolation

The repository contains generic tracked framework code. The resolved local workspace contains all private instance state.

| Data | Allowed location |
|---|---|
| Runtime, schema, UI, Skill, recipes, synthetic examples | Tracked repository |
| Project path and Git registration | Workspace `registry/` |
| Real service descriptor and environment binding | Workspace `launcher.config.json` |
| Instance adapter or GUI entrypoint | Workspace `adapters/` or `entrypoints/` |
| Project shortcut | Workspace `projects/` |
| Logs, reports, cache, backups, imports | Corresponding workspace directories |

Initialize with `python3 scripts/init_dashboard.py`. The default `.local-dashboard/` is ignored; `LOCAL_SERVICE_DASHBOARD_DATA_DIR` may move it. Initialization copies no runtime and creates no sibling project.

Never write real names, paths, ports, commands, URLs, credentials, logs, screenshots, registrations, or reports into `SKILL.md`, `references/`, `recipes/`, `examples/`, tests, defaults, or runtime source. Never use a real project as a public fixture. Put secrets in a process environment or project-local ignored storage, not Dashboard configuration.

Portable export is allowlisted, never a workspace archive. It excludes targets, environment values, logs, reports, cache, observed revisions, and framework code. Adapters are included only when explicitly selected and rejected when they appear to contain a secret or machine path.

If a private failure reveals a generic deficiency, reproduce it with a synthetic temporary fixture before changing the framework. Run `python3 scripts/audit_privacy.py`; it rejects tracked workspace data, user paths, secrets, symlinks, logs, reports, binary artifacts, non-English paths, and generated residue.
