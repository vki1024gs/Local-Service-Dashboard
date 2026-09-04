# Security Policy

## Supported version

Security fixes target the current `main` branch.

## Reporting

Use GitHub private vulnerability reporting when it is enabled for the repository. Otherwise, contact the repository owner privately before opening a public issue. Do not include credentials, access tokens, private paths, logs, or service configuration in a public report.

## Deployment assumptions

- Keep the dashboard bound to `127.0.0.1`.
- Do not expose the dashboard through a public reverse proxy.
- Treat `launcher.config.json` as executable local configuration.
- Keep secrets in the environment or a service-owned ignored file.
- Review every lifecycle and update command before enabling it.
- Do not commit a generated instance.

The per-session API token protects state-changing requests from ordinary browser-origin access; it is not a substitute for host security or safe service commands.
