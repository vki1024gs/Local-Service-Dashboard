# Local Service Dashboard — Agent Notes

This directory is a materialized launcher instance. Read `launcher-skill/SKILL.md` and `ARCHITECTURE.md` before changing it.

- Keep every directory and file name in English; use lowercase kebab-case except conventional `README.md`, `ARCHITECTURE.md`, and `AGENTS.md`.
- Keep instance configuration and runtime state under `dashboard/`.
- Register explicit projects with `dashboard/register_project.py`; keep shortcuts under `projects/`.
- Never copy real project data back into `launcher-skill`.
- Validate configuration with the installed Skill validator and `python dashboard/launcher.py --check-config`.
- Keep the dashboard local-only, token-protected, observational, and free of automatic service restarts.
- Prefer application-level HTTP or a project-owned command health check over bare TCP when a process can listen before its internal runtime is usable.
- Update scripts must use the documented progress protocol, a cross-process single-flight lock, unique temporary files, validation, and atomic replacement.
- Keep the dashboard alive during finite actions and reject competing actions or shutdown until they finish.
