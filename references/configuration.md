# Schema v1 configuration

Workspace `launcher.config.json` is executable local configuration. `scripts/validate_config.py` rejects unknown fields and unresolved registrations. Tracked defaults and examples remain synthetic.

## Descriptor example

```json
{
  "id": "example-web",
  "category": "frontend",
  "project_ref": "example-web",
  "display": {
    "name": "Example Web",
    "name_from": {"file": "package.json", "json_path": "name"},
    "version_from": {"file": "package.json", "key_path": "version", "prefix": "v"}
  },
  "lifecycle": {"start": ["npm", "run", "dev"], "stop": ["npm", "run", "stop"]},
  "health": {"mode": "env", "env_file": ".env", "port_key": "PORT", "scheme": "http", "path": "/health"},
  "url": {"mode": "env", "env_file": ".env", "port_key": "WEB_PORT", "scheme": "http", "path": "/"},
  "ports": [
    {"name": "WebUI", "mode": "env", "env_file": ".env", "port_key": "WEB_PORT", "fallback_port": 3000},
    {"name": "API", "mode": "fixed", "port": 8080}
  ]
}
```

Categories are `static-web`, `frontend`, `backend`, and `service`. Commands accept a string, argument array, or `macos`/`windows`/`default` map. Prefer arrays. Commands execute in the registered project root.

## Separate contracts

- `health` determines readiness: `http`, `tcp`, `env`, `auto`, or project-owned `command`.
- `url` determines Open: a string, `auto`, or an env binding.
- `ports` reports user-relevant endpoints and declared collisions. Use concrete role labels such as `WebUI`, `API`, or `Bridge`.
- `lifecycle.update` exists only for a known safe update workflow.
- registration repository metadata supplies informational upstream state and is not part of the descriptor.

## Version label

`display.version_from` adds the restrained version label shown on a service card. It reads a project-owned JSON or TOML manifest on every monitoring sample, so a successful project update changes the label without editing Dashboard configuration or restarting the Dashboard.

- `file` is required and must remain inside the registered project.
- `format` is optional (`json` or `toml`); when omitted, the `.json` or `.toml` file suffix selects the parser.
- `key_path` is a dot-separated key path and defaults to `version` (for example, `project.version` in `pyproject.toml`).
- `prefix` is optional, limited to eight characters, and is commonly `v`.
- The resolved value must be a non-empty string of at most 64 characters. Missing, invalid, numeric, or oversized values hide the label instead of making the service unhealthy.

Use the application/package version as this source. Do not place a Git commit, remote comparison, or manually copied release value here: registration repository status remains a separate source-control contract.

An env binding may use `env_file`, `port_key`, `fallback_port`, `scheme`, `host`, and `path`. Paths must stay inside the registered project. A port is 1–65535. An explicit environment value wins over a documented fallback. `ports[].editable: false` is accepted as an explicit read-only declaration; this framework deliberately does not mutate a registered project's environment file from the browser.

Use `health.http_probe_interval_seconds` to cache successful HTTP checks while retaining a lightweight TCP sample. Failed HTTP checks are retried. Use `observability` only for documented local diagnostics/log endpoints.

## Update progress

An updater emits one JSON record per line:

```text
LAUNCHER_PROGRESS {"percent":42,"message":"Validating staged release"}
```

Percent is monotonic 0–100. Emit 100 only after post-install verification. Use a cross-process single-flight lock, unique temporary file, validation, and same-filesystem atomic replacement. Nonzero exit must preserve the previous artifact.

## Validation timing and launcher fields

Validation fields are `startup_timeout_seconds`, `stability_seconds`, `shutdown_timeout_seconds`, `poll_interval_seconds`, `action_timeout_seconds`, and `monitor_detection_timeout_seconds`; stability is at least five seconds and other durations are positive.

Launcher host is loopback. `monitor_interval_seconds` is 0.25–5. Set `repository_check_interval_seconds=0` to check each repository once when the Dashboard starts without periodic refresh; positive values must be at least 30 seconds. `exit_when_no_clients_seconds=0` disables idle exit; positive values wait after the last event client leaves and suspend exit during operations. Keep `stop_services_on_exit=false` unless the user explicitly requests coupled shutdown.

Adapters belong under workspace `adapters/<service-id>/`, consume `PROJECT_ROOT` and `DASHBOARD_WORKSPACE_ROOT`, and must not embed real paths.
