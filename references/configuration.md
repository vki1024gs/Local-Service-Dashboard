# Schema v1 configuration

Read [framework.md](framework.md) first. `scripts/validate_config.py` is authoritative and rejects unknown fields.

When a service already exposes structured diagnostics and logs, the optional `observability` object may use `mode: http` with `url`, or `mode: env` with the same project-owned port binding pattern as health. Its relative endpoint fields are `diagnostics_path`, `logs_path`, `events_path`, and `open_path`. Runtime support and validator support must be updated together whenever a framework field is added.

## Service descriptor

```json
{
  "id": "web-app",
  "category": "frontend",
  "project_ref": "web-app",
  "display": {
    "name": "Fallback label",
    "description": "Development frontend",
    "name_from": {"file": "package.json", "json_path": "name"}
  },
  "lifecycle": {
    "start": {"macos": ["npm", "run", "dev"], "windows": ["npm.cmd", "run", "dev"]},
    "stop": {"macos": ["./scripts/stop.sh"], "windows": ["cmd", "/c", "scripts\\stop.bat"]},
    "update": ["git", "pull", "--ff-only"]
  },
  "health": {
    "mode": "env", "env_file": ".env", "port_key": "PORT",
    "scheme": "http", "host": "127.0.0.1", "path": "/health"
  },
  "ports": [
    {"name": "WebUI", "mode": "env", "env_file": ".env", "port_key": "WEB_PORT", "fallback_port": 3000},
    {"name": "API", "mode": "fixed", "port": 8080}
  ],
  "url": "auto"
}
```

Valid categories are `static-web`, `frontend`, `backend`, and `service`. Valid lifecycle actions are `start`, `stop`, and `update`. Commands accept a string, argument array, or `macos`/`windows`/`default` map.

## Update progress protocol

A finite update command may report structured progress on stdout with one JSON object per line:

```text
LAUNCHER_PROGRESS {"percent":42,"message":"Downloading release…"}
```

`percent` is an integer from 0 through 100 and must never move backwards. `message` is a short human-readable current stage. The runtime removes protocol records from ordinary output, streams their values through `services[].operation`, and writes compact progress milestones into the service log.

Update scripts should suppress terminal animation such as curl's progress meter. Use a single-flight lock that survives a dashboard restart, a uniquely named temporary file per invocation, validation before replacement, and an atomic rename into the final location. A nonzero exit must preserve the previously installed artifact. Emit 100 only after post-install verification succeeds. The runtime rejects an update that exits zero without this terminal 100 marker, preventing a prematurely terminated script from being reported as successful.

## Health modes

- `http`: require `url`; use a fixed project-owned health URL.
- `tcp`: require `port`; use a fixed port only when the project has no dynamic source.
- `env`: require `port_key`; optionally set `env_file` (default `.env`), `scheme`, `host`, `path`, and `fallback_port`. The monitor rereads the file. Use `fallback_port` only when the project-owned start command has a documented default for a missing environment variable; an explicit environment value always wins.
- `auto`: discover the most recent localhost URL printed in the launcher-owned log; optionally provide `fallback_url` or `fallback_port`.
- `command`: run a project-owned, read-only readiness command in the registered project directory. Exit code `0` means ready; any other exit code, launch error, or timeout means unhealthy. Use this when a listening socket does not prove that an internal runtime initialized successfully. An optional documented `port` is display-only and does not weaken command readiness.

For HTTP endpoints whose access log would be noisy under real-time monitoring, set `http_probe_interval_seconds` to a positive interval. The monitor then uses a lightweight TCP connection on every dashboard sample and performs the full HTTP request only when the interval expires. A TCP failure is reported immediately, and a failed HTTP result is retried on the next sample rather than cached. Leave the field unset or set it to `0` when every sample must execute the application-level HTTP probe.

Set service `url` to `auto` to reuse the current HTTP health endpoint. This lets the Open button follow an `.env` port change.

## Declared ports and conflicts

Use the optional `ports` array when one service exposes more than one local port. Each entry needs a visible `name` and either `mode: fixed` with `port`, or `mode: env` with `port_key`; environment bindings may also use `env_file` and `fallback_port`. The dashboard rereads environment bindings and compares all declared ports across configured services. A duplicate declaration marks every affected service as abnormal and identifies the other service by name.

Use concrete role labels (`WebUI`, `API`, `Bridge`, or a project-defined endpoint name), not generic categories such as `backend` or `service`. If the service has only the same port already represented by `health`, omit `ports`; the dashboard derives a single `端口 <number>` tag from the health endpoint. If the service exposes multiple ports, declare every user-relevant endpoint so secondary APIs remain visible.

The three related fields have different jobs:

- `health`: the single probe that determines running/readiness state.
- `url`: the destination of the primary Open action; it need not be the health path.
- `ports`: the visible declared endpoint inventory used for cross-service conflict warnings.

Prefer environment bindings over copied numbers whenever the project owns an env setting. A fallback is valid only when it is the project's documented default. A conflict warning means two configured services declare the same port; it does not prove which process currently owns the socket.

This comparison is intentionally limited to registered declarations. It does not scan arbitrary machine ports, reserve ports, or infer undisclosed endpoints.

## Display binding

`display.name` is the fallback. `display.name_from.file` must be a JSON file inside the registered project and `json_path` is a dot-separated key path. The monitor rereads the file, so manifest name changes do not require launcher edits.

## Adapter boundary

Do not generate a wrapper when a project-owned script exists. If an adapter is required, keep it inside `dashboard/adapters/<service-id>/` and reference the registered project only through the `PROJECT_ROOT` environment variable supplied by the runtime.

## Validation timing

Allowed fields are `startup_timeout_seconds`, `stability_seconds`, `shutdown_timeout_seconds`, `poll_interval_seconds`, `action_timeout_seconds`, and `monitor_detection_timeout_seconds`. Stability must be at least 5 seconds.

## WebUI client lifetime

Set launcher-level `exit_when_no_clients_seconds` to a positive number when the dashboard backend should exit after the last `/api/events` WebUI stream disconnects. The countdown resets whenever a WebUI reconnects. Keep `stop_services_on_exit=false` when dashboard lifetime must remain independent from business-service lifetime. A value of `0` or an omitted field disables idle exit.

Idle exit is suspended while any finite lifecycle operation is active. Explicit `/api/shutdown` requests are rejected with `action_in_progress` until the operation finishes.
