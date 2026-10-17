# Safe update progress recipe

Use this recipe only when a registered project already has a finite, non-interactive update workflow and the user wants Dashboard Update control.

Owned files belong in the registered project when they are part of its normal lifecycle, or in ignored workspace `adapters/<service-id>/` for unavoidable instance glue. The recipe adds no framework dependency.

The updater must acquire a project-specific cross-process lock, stage into a unique temporary file on the destination filesystem, validate the staged artifact, atomically replace the target, validate the installed result, and release the lock in a `finally`/trap path. Start must refuse while the same lock is active. Do not use a shared download filename as a lock.

Emit short monotonic progress records:

```text
LAUNCHER_PROGRESS {"percent":10,"message":"Preparing"}
LAUNCHER_PROGRESS {"percent":70,"message":"Validating staged release"}
LAUNCHER_PROGRESS {"percent":100,"message":"Installed and verified"}
```

Do not print credentials or raw tool output. Suppress terminal animation. A failure must leave the previous artifact usable and return nonzero; never emit 100 before final verification.

Adoption:

1. Copy or design the updater only in the registered project or ignored workspace.
2. Reference it with `lifecycle.update`; keep the command relative to the project root or workspace adapter.
3. Run `python3 scripts/validate_config.py <workspace>/launcher.config.json`.
4. Run `python3 scripts/smoke_test.py`; its synthetic action-progress test verifies single-flight rejection, terminal-marker enforcement, ANSI cleanup, and success/failure log boundaries.
5. In an approved test window, force a staged-validation failure and verify the old artifact remains usable before testing a successful update.
