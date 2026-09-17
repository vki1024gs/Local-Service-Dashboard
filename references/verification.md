# Lifecycle verification contract

Use this gate after configuration and whenever a lifecycle command changes. Validation is service-by-service and OS-specific.

## Preconditions

1. Verify only paths explicitly supplied by the user.
2. Confirm that interrupting the service is safe. If it is already healthy before the test, stop and request a test window; never terminate an unidentified process.
3. Require a real readiness contract: application-level HTTP, a project-owned command, or a TCP port only when socket acceptance itself means usable. Process existence alone cannot prove readiness.
4. Prefer existing scripts from the specified path. Record them as `start` and, when needed, `stop`; do not rewrite a script merely for stylistic consistency.

## Required sequence

For every service, run the full sequence with `scripts/verify_lifecycle.py`:

1. **Baseline** — health probe is down and no launcher-owned process is running.
2. **Start** — invoke `start`; health becomes ready within `startup_timeout_seconds`.
3. **Maintain** — health stays ready and the managed process, when applicable, stays alive for `stability_seconds`.
4. **Stop** — invoke configured `stop`, or terminate the launcher-owned process tree; health becomes unavailable within `shutdown_timeout_seconds`.
5. **Second start** — start again and wait for readiness. This proves stop did not leave stale state that prevents a new launch.
6. **Monitor detection** — interrupt the test-owned service without changing desired state; require `stopped-unexpectedly` within the monitoring timeout. Do not auto-restart it.
7. **Recovery start** — start again and require the problem state to clear.
8. **Restart** — execute launcher restart (stop then start); health returns within the startup timeout.
9. **Second maintain** — repeat the stability observation after restart.
10. **Cleanup** — stop and verify health is down. Leave the service stopped unless the user requested a running handoff.

## Pass criteria

A service passes only when every required stage passes in one complete run. Do not combine successful stages from different attempts. A successful browser page load does not replace stop or restart testing.

The verifier writes `dashboard/validation-report.json` with the OS, timestamps, service ID, stage results, and final state. If verification cannot run on Windows or macOS, label that OS `untested`; do not infer cross-platform success from the other OS.

For each configured update command, also require: single-flight rejection, visible progress, unique temporary output, pre-install validation, atomic replacement, preservation of the prior artifact after a forced failure, post-install validation, readable log boundaries, and successful service startup/stability after the update. Repeat the update request while the first synthetic invocation is active and require a deterministic rejection rather than concurrent execution.

## Failure handling

- Start timeout: inspect the service log and the existing start script inside the allowed path.
- Maintain failure: treat early process exit or failed health as a lifecycle defect, even if startup briefly succeeded.
- Stop timeout: add/fix the explicit `stop` command for detached launchers; never use broad process-name killing.
- Restart failure: check stale ports, PID files, locks, and script assumptions inside the allowed path.
- Pre-existing healthy baseline: report `blocked-active`; do not alter that process without explicit permission.
