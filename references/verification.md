# Lifecycle verification contract

Verification is service-by-service and OS-specific. Inspect and operate only paths explicitly supplied by the user.

## Preconditions

1. Confirm interruption is safe. If the service is already healthy, stop and request a test window; never terminate an unknown process.
2. Require real readiness: HTTP, project-owned command, or TCP only when socket acceptance means usable.
3. Prefer project-owned lifecycle scripts and finite stop commands for detached services.

## Required sequence

Run `python3 scripts/verify_lifecycle.py <repository-root> --service <service-id>` (omit `--service` to test all configured services):

1. stopped baseline;
2. start to healthy within timeout;
3. remain healthy for the stability interval;
4. stop to unhealthy;
5. second start to healthy;
6. test-owned interruption detected as unexpected, without auto-restart;
7. external recovery clears the alert;
8. Dashboard restart performs stop then start;
9. second stability interval;
10. cleanup to stopped unless the user requests a running handoff.

All required stages must pass in one run. Reports belong under workspace `reports/`. Label unavailable operating systems `untested`; never infer Windows success from macOS or Linux.

For Update also test: concurrent rejection, visible monotonic progress, unique staging, pre/post validation, atomic replacement, preservation after forced failure, readable logs, and successful startup after update.

Before commit or push run the synthetic suite, privacy audit, Python compilation, and JavaScript syntax check listed in `AGENTS.md`.
