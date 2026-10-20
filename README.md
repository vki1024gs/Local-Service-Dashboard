# Local Service Dashboard

A lightweight localhost dashboard for explicitly registered services on macOS and Windows. The clone is the application: initialization creates only a Git-ignored local workspace and never generates a second Dashboard project.

## Quick start

Requires Python 3.11+ and Git. No Python packages are required.

```text
git clone https://github.com/vki1024gs/Local-Service-Dashboard.git
cd Local-Service-Dashboard
python3 scripts/init_dashboard.py --dry-run
python3 scripts/init_dashboard.py
```

On Windows use `py` instead of `python3`.

Register only a project path you deliberately chose:

```text
python3 dashboard/project_registry.py example-app /explicit/path/to/example-app --visible-name example-app
```

Registration can detect the current Git remote and branch. To use explicit coordinates, add `--git-url <clone-url> --branch <branch>` and, when the clone URL is not already HTTP(S), `--web-url <browser-url>`. Use `--source-url <browser-url>` for a deployed artifact or container whose local folder is not a Git checkout. The validated browser destination appears as “远端项目” under More; HTTP(S) Git clone URLs infer it automatically. Credentials in these URLs are rejected. Use `--no-git` for an untracked project.

Copy a synthetic descriptor from `examples/` into the workspace configuration reported by initialization, then adapt it to the registered project. Validate and launch:

```text
python3 scripts/validate_config.py .local-dashboard/launcher.config.json
python3 dashboard/launcher.py --check-config
./launch-dashboard.command
```

On Windows double-click `launch-dashboard.vbs` for a console-free launch; `launch-dashboard.bat` remains a compatibility entrypoint and delegates to it. Lifecycle, health, registration, and repository-check child processes are also created without a console window. Their captured output remains available through Dashboard logs and errors. The WebUI binds to `127.0.0.1`, uses a random session token for actions, and keeps service health separate from repository-version status.

## Private workspace

The default workspace is `.local-dashboard/` and is ignored by Git. It owns:

- versioned workspace and registration records;
- real service configuration;
- instance-specific adapters and entrypoints;
- project links/pointers;
- logs, reports, cache, backups, and import staging.

To relocate it without editing tracked source:

```text
export LOCAL_SERVICE_DASHBOARD_DATA_DIR=/explicit/private/location
python3 scripts/init_dashboard.py
```

A relative value resolves from the repository root. The same resolver is used by every CLI and the runtime. Do not commit `.env.local`; if you use it to set the variable, load it in your shell or service manager before invoking the Dashboard.

## Service contract

Each service uses a registered `project_ref`. It declares separate concerns:

- `health`: the real readiness contract;
- `url`: the destination of Open;
- `ports`: user-relevant endpoint roles and collision warnings;
- `lifecycle`: explicit start, stop, restart, and optional update behavior;
- registration `repository`: optional informational upstream check.
- `display.version_from`: optional project-owned JSON/TOML version shown as a small card label.

`display.version_from` may instead run a short, read-only version command with a required capture regex. Command results are bounded, cached, and time-limited; the last successful value survives a later transient command failure. Use this for installed binaries and containerized applications that do not publish a local JSON/TOML manifest.

Repository checks use bounded `git ls-remote` and local read-only commands. They run once on first observation by default; use “检查版本” in a service card's More menu for an explicit refresh. A positive `launcher.repository_check_interval_seconds` value of at least 30 seconds opts into periodic checking. Checks never fetch, pull, merge, checkout, or change refs. An unequal revision is shown as “远端版本不同” unless local ancestry already proves “有更新”, “领先”, or “已分叉”. Hovering the notice shows the application version plus the local/remote Git revisions and branches; More links to the validated browser URL. A repository warning does not make a healthy service unhealthy and never creates an Update action.

See [configuration contract](references/configuration.md), [architecture](ARCHITECTURE.md), and [Agent workflow](SKILL.md).

## Portable configuration

Export is allowlisted and excludes project paths, environment values, logs, reports, cache, observed revisions, and framework code:

```text
python3 scripts/config_bundle.py export dashboard-bundle.json
python3 scripts/config_bundle.py export dashboard-bundle.json --adapter example/start.py
```

Import is preview-first. Every project path must be mapped explicitly; unresolved projects leave the current configuration unchanged:

```text
python3 scripts/config_bundle.py import dashboard-bundle.json --map example-app=/explicit/path
python3 scripts/config_bundle.py import dashboard-bundle.json --map example-app=/explicit/path --apply
```

Apply creates a backup and restores it if final validation fails. Portable export is for sharing configuration structure, not secrets or same-machine paths.

## Migrating an older generated instance

Initialize this clone, then preview migration from the old instance:

```text
python3 scripts/migrate_instance.py /explicit/path/to/old-dashboard
```

After reviewing the counts, add `--apply`. Migration backs up the current workspace, copies configuration and instance adapters, converts registrations, excludes runtime/logs/reports/cache, and leaves the source untouched. Do not archive the old instance until the migrated services are validated in an approved test window.

## Reusable Agent kit

`SKILL.md`, `references/`, `recipes/`, and `examples/` are public tracked design inputs. They must remain generic and synthetic. An Agent reads them, then writes real descriptors and glue only into the ignored workspace or an explicitly registered project. The compatibility command `scripts/create_launcher.py` initializes this clone in place; it no longer accepts or creates a destination.

## Verification

```text
python3 scripts/smoke_test.py
python3 scripts/audit_privacy.py
python3 -m py_compile dashboard/*.py scripts/*.py
node --check dashboard/ui/app.js
```

`scripts/verify_lifecycle.py` performs the stopped → start → stable → stop → restart → stable sequence for configured synthetic or real services. Use it for real services only in an approved test window; it never authorizes stopping an unidentified process.

CI runs synthetic and privacy gates on macOS, Linux, and Windows. The privacy audit rejects tracked local workspaces, registrations, machine paths, logs, reports, secrets, non-English paths, and generated residue.

## License

MIT. See [LICENSE](LICENSE).
