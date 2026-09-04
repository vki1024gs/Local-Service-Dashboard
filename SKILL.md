---
name: local-service-launcher
description: Build, configure, validate, or update a lightweight cross-platform Windows/macOS real-time Web dashboard and launcher for explicitly supplied local services using a fixed privacy-isolated framework. Use when Codex needs to register projects outside the reusable skill, organize existing lifecycle scripts, continuously detect stops and recovery, prove lifecycle behavior, or generate a portable launcher. Never scan for projects, infer paths, lock business ports, impose automatic restarts, or store any real project path, name, port, command, log, registration, or report inside the skill package.
---

# Local Service Launcher

Create one launcher instance from the bundled framework for services and destinations explicitly named by the user. Treat the framework layout and schema as mandatory; do not let the Agent design an alternative launcher from prose.

## Scope boundary

- Require the user to provide every service/project path and the launcher output path.
- If either is missing, ask for it before reading project files or creating the launcher.
- Treat each supplied path as an authorization boundary. Inspect only that path and the files beneath it that are necessary to configure the named service.
- Never scan the current workspace, home directory, parent directories, sibling directories, common project locations, ports, or running processes to discover additional services.
- Never add a discovered-but-unrequested service. Configure only the services the user explicitly names.

## Privacy boundary

- Read [references/privacy.md](references/privacy.md) before handling any real project.
- Keep the installed Skill generic and reusable. Never write project names, paths, ports, repository URLs, lifecycle commands, environment values, service IDs, logs, validation reports, screenshots, or registration links into `SKILL.md`, `agents/`, `references/`, `scripts/`, or `assets/`.
- Write all project-specific descriptors, registry links/pointers, adapters, logs, reports, and UI state only inside the explicit launcher instance destination.
- Never run `register_project.py` or the WebUI from `assets/launcher-template/`; the template intentionally lacks `dashboard/.launcher-instance` and refuses real registration or execution.
- When improving the Skill after a project-specific failure, convert the lesson into a generic rule and reproduce it with synthetic temporary fixtures. Do not copy the project's files, commands, paths, or log excerpts into the Skill.
- When runtime support gains a configuration field, update the generic validator, configuration reference, and synthetic regression coverage in the same change; never leave an instance-only schema fork.
- Do not persist project information as Skill examples, Skill notes, or Skill-specific memory. Keep temporary test artifacts outside the Skill and remove or abandon them after validation.

## Workflow

1. Confirm the explicit service paths and launcher output path before editing anything.
2. Inspect only the specified service paths.
   - Identify the real working directory, start command, every documented listening port, the readiness endpoint, the user-facing open URL, update command, and shutdown behavior.
   - Read port values only from project-owned documentation, environment examples/current local env, manifests, lifecycle scripts, or explicit user input. Do not infer or discover additional ports from the machine.
   - Treat readiness, navigation, and port inventory as separate facts: `health` decides service state, `url` decides the Open action, and optional `ports` exposes declared endpoints and configuration conflicts.
   - Inspect relevant package scripts, existing `.command`/`.bat` files, compose files, and health endpoints only inside those paths. Do not guess or broaden the search.
   - Reuse working lifecycle scripts already present in the specified path. Wrap or replace them only when validation proves they cannot meet the lifecycle contract.
3. Read [references/framework.md](references/framework.md), then materialize the framework with `python scripts/create_launcher.py <exact-destination>`. Do not manually edit or copy project data into the Skill template.
4. Work only inside the created instance, identified by `dashboard/.launcher-instance`. Register each explicit project with `<destination>/dashboard/register_project.py`, passing an English `--visible-name`. Prefer its symlink or Windows junction mode; accept its pointer fallback.
5. Replace the example with schema-v1 entries from [references/configuration.md](references/configuration.md). Use only the four fixed categories and documented schema fields. When a service exposes multiple ports, declare every user-relevant endpoint in `ports` with a concrete role label and its project-owned source.
6. Preserve OS-specific lifecycle commands when they differ. Keep commands relative to the registered project root and prefer project-owned scripts.
7. Validate with `python scripts/validate_config.py <destination>/dashboard/launcher.config.json`. Treat unknown fields, unregistered references, and old free-form `cwd`/`start` layouts as errors.
8. Read [references/verification.md](references/verification.md), obtain any required test window, then run `python scripts/verify_lifecycle.py <launcher-directory>` for every configured service.
9. Fix only the failing lifecycle stage and repeat the complete verification sequence. Do not mark a service complete from a successful start alone.
10. Read [references/monitoring.md](references/monitoring.md), start the WebUI, and prove that a service interruption appears in the live stream and that an external recovery clears the alert.
11. Run the drift test from `framework.md` when project-owned name or port bindings are configured. Also verify that declared duplicate ports mark every affected service and identify the conflicting service; do not treat this declaration warning as proof that an unknown process owns the port.
12. Run `python <destination>/dashboard/launcher.py --check-config`, then start it with `python <destination>/dashboard/launcher.py --no-browser` and verify the API/UI if execution is safe.
13. Run `python scripts/audit_privacy.py` against the reusable Skill and require it to pass.
14. Tell the user how to launch the instance and report lifecycle, monitoring, drift, and privacy-audit results: `launch-dashboard.command` on macOS or `launch-dashboard.bat` on Windows.

## Configuration rules

- Read [references/configuration.md](references/configuration.md) whenever creating or changing service entries.
- Keep `schema_version: 1`; never introduce ad-hoc fields, path variables, category names, or per-service directory layouts.
- Store only `project_ref` in a service descriptor. Resolve the real path through `dashboard/registry/projects/` and the framework registrar.
- Use `static-web`, `frontend`, `backend`, or `service`; do not invent a fifth category.
- Store commands under `lifecycle`. Use argument arrays where possible and keep them relative to the project root.
- Prefer `display.name_from` and `health.mode=env` when project manifests own the name and port. Use `url: auto` to follow the current HTTP endpoint.
- Keep `health`, `url`, and `ports` semantically distinct. Configure one real readiness probe in `health`; configure the destination users should visit in `url`; use `ports` only as the visible endpoint inventory and cross-service declaration check.
- When a service has only the same single port already represented by `health`, omit `ports`; the runtime displays that health port automatically. When it exposes multiple ports, list all user-relevant endpoints in `ports` so secondary APIs are not hidden.
- Name port entries by concrete endpoint role such as `WebUI`, `API`, `Bridge`, or another project-defined function. Do not use vague implementation categories such as `backend` or `service` as visible port labels.
- Prefer `ports[].mode=env` when a project-owned environment file controls the value. Use `mode=fixed` only for a documented fixed port, and set `fallback_port` only when the project documents that exact default.
- Treat a duplicate declared port as a configuration risk even if current health probes succeed. Surface every affected service and its conflicting peer; do not scan arbitrary ports or claim which process actually owns the socket.
- Configure `lifecycle.stop` when an existing start script detaches, delegates to a service manager, or otherwise exits before the localhost service stops.
- Never write a wrapper merely to normalize naming. If a wrapper is unavoidable, place it under `dashboard/adapters/<service-id>/` and use the supplied `PROJECT_ROOT`; reject literal original-project paths in adapters.
- Implement restart as the verified stop-then-start sequence; do not assume that repeating the start command performs a restart.
- Add `update` only when the project has a known safe update workflow. Never invent destructive update commands.
- Put secrets in the machine environment or a service-local ignored env file. Never write secrets into the launcher config.
- Never back-propagate an instance's `dashboard/launcher.config.json`, `dashboard/registry/`, `dashboard/adapters/`, `dashboard/logs/`, `dashboard/.launcher-instance`, `dashboard/validation-report.json`, or `projects/` into the Skill.
- Keep the server bound to `127.0.0.1`. Do not weaken the per-session API token check.

## Runtime boundaries

- Treat the WebUI as an observational dashboard with explicit control buttons, not a service supervisor.
- Never bind, reserve, lock, or protect a configured business-service port. Use ports only for HTTP/TCP health probes.
- Never automatically restart a stopped service. Record the interruption and recovery; let the user or an external Agent control maintenance restarts.
- Expect external Agents to stop, rebuild, and restart services. Follow the observed health state even when the process PID or owner changes.
- Closing the browser or dashboard process must not stop business services by default. Set `launcher.stop_services_on_exit` only when the user explicitly requests coupled shutdown.
- Stop uses a process group on macOS and a process tree on Windows, so start commands must not target unrelated shared process groups.
- The GUI is intentionally configuration-only. Do not add an arbitrary command editor to the browser UI.
- Treat `dashboard/launcher.config.json` as executable local configuration because its commands are launched by the host process.

## Verification gate

- Treat lifecycle verification as mandatory for each service and each configured operating system that is available for testing.
- Require a stopped baseline. If the target port is already active, do not stop an unknown or pre-existing process; report the blocked verification and ask for a test window.
- Require all four stages to pass: start to healthy, remain healthy for the configured stability interval, stop to unhealthy/closed, and restart to healthy followed by another stability interval.
- Leave the service stopped after verification unless the user explicitly asks otherwise.
- Save `validation-report.json` inside the generated launcher's `dashboard` directory. Report failures with the failing stage and relevant service log; never claim an untested OS passed.
- Require the live monitor to detect an unexpected stop within two configured monitor intervals and show recovery without automatically launching anything.

## Extending the framework

Change `dashboard/launcher.py`, `dashboard/register_project.py`, the schema, or `dashboard/ui/` only for capabilities that cannot be represented by framework v1. Never fork the framework for one service. Keep stdlib-only Python compatibility unless the user explicitly accepts dependencies. Re-run config validation and `scripts/smoke_test.py` after runtime changes.
