---
name: local-service-launcher
description: Configure, validate, migrate, or extend this lightweight cross-platform localhost service Dashboard using its privacy-isolated local workspace. Use for explicit service registration, lifecycle controls, health/port monitoring, safe updates, Git upstream status, portable configuration, or launcher verification. Never create a second Dashboard project, scan for projects, infer paths, store real instance data in Git, lock business ports, or impose automatic restarts.
---

# Local Service Dashboard

This repository is the application and the canonical Agent kit. Real instance data belongs in its ignored local workspace; runtime source remains tracked once.

## Mandatory boundaries

- Read `references/privacy.md` before handling a real project.
- Require every service path explicitly. Never scan a home, parent, sibling, common-project, port, or process location to discover services.
- Initialize with `python3 scripts/init_dashboard.py`; never generate or copy a sibling Dashboard.
- Store real descriptors, registrations, Git coordinates, adapters, entrypoints, environment values, logs, reports, cache, and backups only in the resolved workspace.
- Keep tracked `examples/` and `recipes/` synthetic. Use them as inputs; never customize them into a real instance.
- Keep the Dashboard bound to loopback and preserve the per-session action token.

## Workflow

1. Run `python3 scripts/init_dashboard.py --dry-run`, review the path, then initialize. The default is `.local-dashboard/`; `LOCAL_SERVICE_DASHBOARD_DATA_DIR` may relocate it.
2. Inspect only user-supplied project paths. Identify the project-owned start/stop/update commands, real readiness signal, Open URL, and every documented user-relevant port.
3. Register each path with `python3 dashboard/project_registry.py <project-ref> <path>`. Use English lowercase identifiers. Accept optional detected or explicit Git remote/branch; reject embedded credentials.
4. Read `references/configuration.md`. Edit workspace `launcher.config.json`; do not put paths in service descriptors.
5. Reuse project-owned lifecycle scripts. If glue is unavoidable, place it in workspace `adapters/<service-id>/`, consume `PROJECT_ROOT` and `DASHBOARD_WORKSPACE_ROOT`, and never embed the target path.
6. Validate with `python3 scripts/validate_config.py <workspace>/launcher.config.json` and `python3 dashboard/launcher.py --check-config`.
7. Read `references/verification.md`; in an approved test window run the mandatory lifecycle sequence for each service and available OS.
8. Read `references/monitoring.md`; prove an unexpected stop and external recovery appear without automatic restart.
9. Run `python3 scripts/audit_privacy.py` and the synthetic test suite before commit or push.

## Configuration rules

- `health`, `url`, `ports`, lifecycle `update`, and registration `repository` have different meanings. Do not substitute one for another.
- Use `static-web`, `frontend`, `backend`, or `service`; do not invent categories or schema fields.
- Use argument arrays where possible and keep commands relative to the registered project root.
- Prefer application-level HTTP or project-owned command readiness. Use TCP only when accepting a socket is the true contract.
- Use concrete port role labels such as `WebUI`, `API`, or `Bridge`, never vague visible labels such as “backend” or “service”.
- When a card should show an application version, bind `display.version_from` to a project-owned JSON/TOML version field. Never duplicate the value manually or confuse it with Git upstream status.
- When no manifest exists, `display.version_from.command` may call a read-only version query with a required capture regex, bounded timeout, and refresh cache. Do not use lifecycle or mutating commands as version probes.
- Duplicate declared ports are configuration risks. Report every affected service without claiming an unknown OS process owns the port.
- Add Update only for a known safe project-owned workflow. It must be single-flight, emit `LAUNCHER_PROGRESS`, stage unique temporary output, validate it, and atomically replace the target.
- Restart is verified stop then start. Never kill an unidentified listener or infer ownership from a PID alone.
- Secrets belong in the process environment or project-local ignored storage, never Dashboard configuration or bundles.

## Repository status

Optional Git metadata is stored in the private registration record. A browser destination must use validated `repository.webUrl`; infer it only from an HTTP(S) clone URL, otherwise require `--web-url`. A non-checkout artifact or container may use validated top-level `sourceUrl` solely as its More-menu destination; it must not fabricate Git status. Status checks are bounded, cached, background, and non-mutating. They run once on first observation by default and then only on explicit user refresh; a positive configured interval explicitly opts into periodic checking. They may use `ls-remote` and local read-only inspection, but never fetch, pull, checkout, merge, update refs, or modify the worktree. Show `update_available` only when ancestry is already provable; otherwise show that the remote is different. A drift notice must expose both local and remote revisions and the compared branches, while the application version remains a separate `display.version_from` value. Repository availability never changes service health and never enables lifecycle Update.

On Windows, launch through `launch-dashboard.vbs` to avoid a console window; `.bat` is compatibility-only and may flash its own shell. Dashboard-owned subprocesses must use the shared hidden-process policy while preserving captured diagnostics and process-group control. Background Git must also disable terminal and credential-manager interaction.

## Migration and bundles

- Preview legacy migration with `scripts/migrate_instance.py`; apply only after synthetic tests pass. Preserve the source.
- Portable export uses `scripts/config_bundle.py export`. It includes sanitized configuration, registration identities, optional public Git coordinates, and only explicitly selected adapters.
- Import requires explicit `project-ref=/path` mappings, validates in a temporary workspace, previews first, backs up before apply, and rolls back on failure. Never scan for unresolved projects.

## Verification gate

Require all of the following:

```text
python3 scripts/smoke_test.py
python3 scripts/audit_privacy.py
python3 -m py_compile dashboard/*.py scripts/*.py
node --check dashboard/ui/app.js
```

For a real service, require stopped baseline, start to healthy, stability interval, stop to unhealthy, restart to healthy, second stability interval, interruption detection, and external recovery. Leave the service stopped unless the user explicitly requests otherwise. Never claim an unavailable OS passed.

## Framework changes

Change runtime, schema, documentation, synthetic coverage, and this Skill in the same commit when adding a generic capability. Keep the runtime Python-stdlib-only unless the user explicitly accepts a dependency. A project-specific failure may become a generic rule only after reproduction with synthetic fixtures; never copy private names, paths, commands, URLs, or logs into this repository.
