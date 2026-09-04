# Architecture

## Purpose

This repository contains a reusable framework and a generator. It is not a deployed dashboard and must not contain machine-specific service data.

## Source layout

```text
local-service-dashboard/
├── AGENTS.md
├── ARCHITECTURE.md
├── README.md
├── SKILL.md
├── LICENSE
├── agents/
├── assets/
│   └── launcher-template/
├── references/
└── scripts/
```

- `assets/launcher-template/` is the generic source copied into a new private instance.
- `scripts/create_launcher.py` is the only supported materialization path.
- `scripts/validate_config.py` validates the fixed schema and registered references.
- `scripts/verify_lifecycle.py` proves lifecycle and monitoring behavior.
- `scripts/audit_privacy.py` rejects private runtime artifacts and absolute user paths.
- `references/` defines configuration, monitoring, verification, and privacy contracts.

## Deployment boundary

The generator copies the template into a user-chosen directory outside this repository. Only that generated instance may contain:

- project registrations and pointers;
- lifecycle commands and real ports;
- adapters;
- runtime logs and validation reports;
- the `.launcher-instance` marker.

The repository itself must remain synthetic and portable. A generated instance links back to this repository for maintenance instructions, but its runtime files are independent copies.

## Runtime model

The generated Python process serves a localhost WebUI and JSON API, supervises only processes started through the dashboard, and probes only explicitly configured health endpoints. Readiness is authoritative; a launcher-owned PID is optional.

`health` answers whether a service is ready. `url` supplies the primary Open destination. `ports` is a declared endpoint inventory used to expose potential configuration conflicts. These concepts remain separate.

The monitor reports unexpected stops and later recovery. It does not automatically restart services or scan the machine for unknown projects, ports, or processes.

## Trust model

`launcher.config.json` is executable local configuration because lifecycle commands run on the host. The server binds to `127.0.0.1`, state-changing API requests require a per-session token, and secrets belong in the environment or a service-owned ignored file.

## Change rule

A framework capability change is complete only when runtime, validator, configuration reference, synthetic regression coverage, and deployment documentation agree. Private instance fixes must first be generalized and reproduced with synthetic fixtures before entering this repository.
