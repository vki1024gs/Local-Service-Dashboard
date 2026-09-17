# Agent Guide

Read `SKILL.md`, `ARCHITECTURE.md`, and the relevant file under `references/` before changing code or configuring an instance.

## Repository boundary

- This repository is reusable framework source, not a dashboard instance.
- Never add real project names, paths, repository URLs, ports, commands, environment values, logs, screenshots, registrations, or validation reports.
- Never run the template directly or add `assets/launcher-template/dashboard/.launcher-instance`.
- Use only synthetic temporary fixtures for tests.
- Keep all file and directory names in English. Prefer lowercase kebab-case except conventional uppercase documentation names.

## New deployment

1. Obtain the exact instance destination and every project path from the user.
2. Do not scan parent folders, common project locations, ports, or processes.
3. Run `python scripts/create_launcher.py <new-destination>`.
4. Register only supplied projects with the generated `dashboard/register_project.py`.
5. Configure lifecycle commands, readiness, navigation URL, and documented ports from project-owned sources.
6. Add `lifecycle.update` only for a known safe project update workflow.
7. Validate config, prove the complete lifecycle, and verify live stop/recovery monitoring.

## Framework changes

- Preserve the fixed schema and localhost-only, token-protected runtime.
- Keep readiness, Open URL, and declared port inventory separate.
- Prefer application-level HTTP or a project-owned command health check over bare TCP when a process can listen before its internal runtime is usable.
- Do not add project discovery, arbitrary command editing, port reservation, or automatic restart.
- Update runtime, validator, schema/reference docs, synthetic tests, and README together when behavior changes.
- Keep Python runtime dependencies standard-library-only unless a maintainer explicitly changes that policy.
- Require update scripts to implement `LAUNCHER_PROGRESS`, a cross-process single-flight lock, unique temporary files, validation, and atomic replacement.
- Keep the dashboard alive during finite operations and reject conflicting service actions or shutdown until completion.
- Render lifecycle failures in the application UI with cleaned logs; do not use native browser alerts.

## Required checks

```bash
python scripts/smoke_test.py
python scripts/audit_privacy.py
python scripts/validate_config.py assets/launcher-template/dashboard/launcher.config.json
python -m py_compile assets/launcher-template/dashboard/launcher.py
python -m py_compile assets/launcher-template/dashboard/register_project.py
```

If Node.js is available, also run:

```bash
node --check assets/launcher-template/dashboard/ui/app.js
```

Report macOS and Windows verification separately. Never claim an unavailable operating system was tested.
