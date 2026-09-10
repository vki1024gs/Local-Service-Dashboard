# Real-time monitoring contract

Keep the WebUI observational. It may invoke lifecycle commands only after explicit button actions.

## Required behavior

- Stream service snapshots continuously from `/api/events`; do not rely on manual refresh.
- Use `launcher.monitor_interval_seconds` between 0.25 and 5 seconds; default to 1 second.
- Probe all configured services concurrently so one slow health endpoint does not delay unrelated cards.
- Allow HTTP services to use lightweight TCP checks between less frequent full HTTP probes, so real-time dashboards do not flood project-owned access logs. Never cache a failed HTTP result for the full interval.
- Show stream connectivity, last sample time, healthy/problem/stopped counts, last transition time, and a bounded transition history. Keep launcher-owned PID available to diagnostics when present, but do not reserve primary card space for it because externally managed services legitimately report no PID.
- Show an active finite operation directly on its service card, including its stage and determinate percentage when supplied. Update the existing progress elements in place so frequent samples do not recreate a hovered card.
- Disable every conflicting action for that service while an operation is active. Do not rely on the clicked button's temporary disabled state.
- Mark a service as unexpected-stop when it was previously healthy or was explicitly started from the dashboard and becomes unavailable.
- Clear the active alert and record a recovery event when an external Agent brings the service back.
- Do not reserve the business port, create port locks, automatically restart, or reject an externally changed PID.
- Keep services running when the dashboard exits unless the user explicitly enables `stop_services_on_exit`.
- When `exit_when_no_clients_seconds` is enabled, start its countdown only after the last live WebUI event stream disconnects. A reconnect cancels the idle condition. Exiting the dashboard this way must not stop business services when `stop_services_on_exit=false`.
- Suspend idle exit and reject explicit dashboard shutdown while a finite action is active.
- Render action failures in an application dialog with the meaningful error, error type, exit code when available, and a direct path to the cleaned service log. Do not use the browser's native `alert()` for lifecycle errors.
- Remove ANSI control sequences and terminal progress animation from the displayed log. Keep clear action start/success/failure/timeout boundaries and elapsed time.

## Acceptance test

1. Open the live stream and confirm at least two snapshots arrive at the configured interval.
2. Start a test service and observe `ready`.
3. During an approved test window, interrupt it without changing the dashboard's desired state.
4. Confirm `problem=stopped-unexpectedly` appears within two monitor intervals.
5. Restart it externally or with a new start action; confirm the card returns to `ready` and the event list records recovery.
6. Stop the dashboard process and confirm the business service remains running when `stop_services_on_exit=false`.
7. Run a synthetic update that emits at least two `LAUNCHER_PROGRESS` records; confirm the card advances without hover jitter and competing actions are rejected.
8. Attempt to exit during the update; confirm the dashboard remains available, then exits normally after completion.

Do not perform the interruption test against an unidentified or pre-existing process.
