# Local Service Dashboard: unified repository and private workspace PRD

Status: Implemented and locally verified
Date: 2026-10-17
Priority: P0/P1
Target: `Local-Service-Dashboard`

## 1. Summary

Local Service Dashboard must stop using a clean public framework clone plus a separately generated private Dashboard project. A cloned repository must itself be the runnable Dashboard application. Machine-specific registrations, service descriptors, adapters, lifecycle helpers, GUI wrappers, logs, reports, caches and Git-version observations must live in one explicit local workspace that Git ignores.

The tracked repository will contain only reusable application code, schemas, examples, documentation and verification tools. The ignored workspace will contain all user-authored or machine-derived instance data. Framework updates must change tracked code without overwriting the local workspace. Registering a service must connect the tracked runtime to the ignored workspace; it must never copy the Dashboard application or write a real service into tracked files.

This design removes the reason for maintaining separate “public” and “personal” Dashboard projects while preserving the privacy guarantee that motivated the split.

## 2. Current facts

There are currently three drifting surfaces:

1. The Git repository contains reusable framework source and instructs an Agent to generate a second Dashboard directory.
2. The desktop Dashboard is a non-Git private instance with real registrations, service-specific adapters, launch wrappers, logs and verification reports.
3. The installed reusable skill contains newer generic runtime capabilities than the Git repository, while the desktop instance is close to but not identical to that skill version.

The duplicate project is therefore expected behavior under the current contract, not an isolated Agent mistake. The current structure also creates three copies of runtime code that can drift independently.

The existing registrar stores project paths through links or pointer files but has no repository metadata contract and no Git-version status model.

## 3. Problem statement

### 3.1 Duplicate application

After cloning the repository, the documented workflow runs `create_launcher.py <destination>`. The result is a framework repository plus a second Dashboard project. Users and Agents cannot easily tell which copy owns runtime code, documentation or upgrades.

### 3.2 Privacy is achieved by project duplication

The current clean/private split prevents machine paths and service configuration from reaching Git, but only by placing all usable state in another project. Privacy must instead be enforced by an explicit storage boundary and repository gates.

### 3.3 Local scripts have no single governed home

Service-specific adapters, update helpers, stop helpers, GUI wrappers and validation artifacts are currently placed inside a generated instance. A unified repository needs a stable ignored location for all of them without mixing them with tracked framework modules.

### 3.4 Registration lacks source-version awareness

Registration does not retain an optional Git remote, branch or observed revision. The Dashboard cannot distinguish a service that is current from one whose upstream repository has a newer revision.

## 4. Goals

### P0 goals

- A clone is the Dashboard. Initialization must not create or require a sibling project.
- All machine-specific service data and scripts live under one ignored local workspace by default.
- The local workspace may be relocated with one environment variable without changing tracked files.
- Pulling or replacing tracked framework code must not overwrite local registrations, configuration, scripts or history.
- Runtime code has one tracked source. It must not be copied into the local workspace.
- Git and CI gates must fail if a real path, registration, service configuration, log, report, secret or local workspace artifact becomes trackable.
- Existing desktop instance data must have a previewable, non-destructive migration path.

### P1 goals

- Registration is an independent module shared by the CLI, runtime and validator.
- The Git repository retains a complete reusable Agent kit: skill instructions, contracts, generic recipes and synthetic examples suitable for a fresh clone with no prior context.
- A registration may record a detected or explicitly supplied Git remote and branch.
- The Dashboard performs bounded, cached, read-only upstream checks and marks services with a newer remote revision.
- Registration data and service configuration can be exported and imported without bundling framework code.
- Agents receive one unambiguous cold-start contract and never receive instructions to create a second Dashboard.

### P2 goals

- A browser-assisted registration editor may be added after the CLI and data contracts are stable.
- Optional semantic release/tag comparison may supplement commit comparison for repositories that publish reliable version tags.
- Optional encrypted secret references may be considered separately; secrets are not part of this PRD.

## 5. Non-goals

- Discovering projects by scanning disks, ports, processes or common directories.
- Automatically registering a project merely because it exists on the machine.
- Automatically running `git pull`, `git fetch`, `checkout`, `reset`, package installation or service updates.
- Treating a remote revision difference as permission to update a service.
- Committing or publishing the user’s service registry.
- Copying registered projects into the Dashboard repository.
- Moving project-owned lifecycle scripts into the Dashboard when they already belong to the registered project.
- Providing a general-purpose command editor in the browser.
- Supporting arbitrary remote hosts as Dashboard HTTP bind addresses.

## 6. Terminology

- **Framework**: tracked Dashboard runtime, UI, schemas, generic tools and documentation.
- **Local workspace**: ignored machine-local Dashboard state owned by one clone.
- **Registered project**: an explicitly supplied project directory referenced by a stable `project_ref`.
- **Service descriptor**: local configuration that maps a registered project to lifecycle, readiness, navigation and port behavior.
- **Project-owned script**: a script stored in the registered project and maintained with that project.
- **Instance adapter**: a user-specific helper needed only by this Dashboard instance.
- **Repository status**: read-only Git metadata reported for a registered project; it is not service health.
- **Service health**: runtime readiness derived from the configured health contract; it is independent from repository status.

## 7. Target architecture

```text
Local-Service-Dashboard/                 # one Git checkout and runnable app
├── AGENTS.md                            # tracked framework/agent contract
├── SKILL.md                             # tracked canonical Agent workflow
├── agents/                              # tracked skill/agent metadata
├── README.md                            # tracked clone, initialize, run, upgrade guide
├── ARCHITECTURE.md                      # tracked boundaries
├── dashboard/                           # tracked runtime source, one copy only
│   ├── launcher.py
│   ├── project_registry.py              # registration and path resolution module
│   ├── repository_status.py             # bounded read-only Git checks
│   └── ui/
├── defaults/
│   └── launcher.config.example.json     # tracked synthetic defaults only
├── references/                          # tracked schema and behavior contracts
├── recipes/                             # tracked optional generic integrations
├── examples/                            # tracked synthetic example projects/configs
├── scripts/
│   ├── init_dashboard.py                # creates local workspace only
│   ├── migrate_instance.py              # preview/apply migration
│   ├── validate_config.py
│   ├── verify_repository.py
│   └── ...
├── docs/
└── .local-dashboard/                    # ignored default workspace
    ├── workspace.json                   # versioned workspace identity
    ├── launcher.config.json             # real local service descriptors
    ├── registry/
    │   └── projects/<project-ref>.json  # path and optional Git metadata
    ├── adapters/<service-id>/            # instance-only helper scripts
    ├── entrypoints/                     # instance-only GUI wrappers/builds
    ├── projects/                        # optional readable links/pointers
    ├── logs/
    ├── reports/
    ├── cache/repository-status/
    ├── backups/
    └── imports/
```

The default workspace is `<repository>/.local-dashboard`. The entire directory is ignored by Git. Users may set `LOCAL_SERVICE_DASHBOARD_DATA_DIR` to an absolute or repository-relative directory. Relative values resolve from the repository root. One resolver module must be used by initialization, registration, validation, runtime, migration, import/export and tests.

No local path may be stored in a tracked file. No tracked runtime module may be copied into `.local-dashboard`.

The repository-resident skill, references, recipes and examples are part of the product. They remain tracked and versioned with the runtime so a newly cloned repository contains everything an Agent needs to design a local instance without downloading a second framework or relying on hidden machine memory.

## 8. Data classification and ownership

| Data | Tracked | Location | Owner |
| --- | --- | --- | --- |
| Runtime and WebUI source | Yes | `dashboard/` | Framework |
| Agent skill and contracts | Yes | `SKILL.md`, `agents/`, `references/` | Framework |
| Generic recipes and synthetic examples | Yes | `recipes/`, `examples/`, `defaults/` | Framework |
| Schemas and synthetic examples | Yes | `defaults/`, `references/` | Framework |
| Real launcher configuration | No | workspace `launcher.config.json` | User instance |
| Project path and visible shortcut | No | workspace `registry/`, `projects/` | User instance |
| Optional repository URL/branch | No | workspace registration record | User instance |
| Service-specific adapter/helper | No | workspace `adapters/<service-id>/` | User instance |
| Project-owned lifecycle script | In that project only | registered project | Registered project |
| Dashboard GUI wrapper/build | No | workspace `entrypoints/` | User instance |
| Logs, reports and caches | No | workspace `logs/`, `reports/`, `cache/` | Runtime |
| Export bundle | No by default | user-selected destination | User |
| Framework verification fixtures | Yes | test directories, synthetic only | Framework |

## 9. Local workspace contract

### R01 — deterministic resolution (P0)

All commands resolve the workspace in this order:

1. `LOCAL_SERVICE_DASHBOARD_DATA_DIR` process environment value;
2. repository-root `.env.local` value, if that ignored file is introduced;
3. `<repository>/.local-dashboard` default.

The runtime must report the resolved workspace path in diagnostics, but the browser must not expose it unless explicitly requested from a localhost-authenticated diagnostics view.

### R02 — marker and schema version (P0)

The workspace contains `workspace.json` with at least:

```json
{
  "schemaVersion": 1,
  "documentType": "local-service-dashboard-workspace",
  "applicationId": "local-service-dashboard",
  "createdAt": "RFC3339 timestamp"
}
```

Unknown major versions must fail with a clear incompatibility message. Initialization must never silently replace an incompatible workspace.

### R03 — initialization in place (P0)

`scripts/init_dashboard.py` creates the workspace directories, marker and local configuration from synthetic defaults. It does not copy repository code, create another Git repository or require a destination project directory.

Initialization must support:

- `--dry-run` with an exact plan;
- idempotent no-op when already initialized;
- `--data-dir` as a one-run equivalent of the environment setting;
- atomic writes and rollback on partial failure;
- refusal to initialize inside a registered project path;
- a final Agent-readable summary of the workspace, registration command and next validation step.

### R04 — Git-ignore enforcement (P0)

The root `.gitignore` must ignore:

- `/.local-dashboard/`;
- `/.env.local`;
- generated GUI application bundles;
- ordinary logs, reports, caches and temporary files.

Repository verification must additionally inspect `git ls-files` and fail if tracked content matches workspace artifacts, pointer records, absolute user paths, secrets, real registrations, logs or reports. Relying only on `.gitignore` is insufficient because `git add -f` can bypass it.

### R05 — safe framework upgrade (P0)

`git pull --ff-only` updates tracked framework source only. Startup, build and cleanup scripts must not delete or rewrite the workspace. If a workspace schema migration is required, the application must preview it, back up exact prior bytes, migrate sequentially, validate the full result and restore on failure.

## 10. Registration module

### R06 — shared module (P0)

`dashboard/project_registry.py` is the only implementation allowed to:

- resolve a `project_ref` to a path;
- validate the target directory;
- create, replace, inspect or remove a registration;
- create optional readable links/pointers;
- read registration metadata;
- serialize registration records atomically.

The CLI, runtime and validator must import this module rather than reimplement pointer rules.

### R07 — registration record (P0)

Each workspace record uses a versioned schema:

```json
{
  "schemaVersion": 1,
  "documentType": "registered-project",
  "projectRef": "example-app",
  "visibleName": "example-app",
  "target": "/machine/local/path",
  "repository": {
    "url": "https://example.invalid/owner/repository.git",
    "branch": "main",
    "remote": "origin"
  }
}
```

`repository` is optional. The target and repository metadata are private workspace data and must never be copied to `launcher.config.json` or tracked files.

### R08 — explicit registration (P0)

The registration CLI requires an explicit `project_ref` and explicit target path. It may inspect only that target. It must not scan parent folders or infer other projects.

If the target is a Git worktree, the registrar may propose the configured upstream URL, branch and remote. The user or Agent must be able to override or disable repository tracking explicitly. Credentials embedded in URLs must be rejected and never persisted.

Replacing or removing a registration requires a preview of affected shortcuts and service descriptors. Removing a registration referenced by a service must fail unless the service descriptor is removed or an explicit coordinated migration is performed.

### R09 — local scripts (P0)

Every instance-only script belongs under workspace `adapters/<service-id>/` or `entrypoints/`. Runtime commands may reference these helpers through a workspace variable supplied by the launcher, such as `DASHBOARD_WORKSPACE_ROOT`; tracked configuration must not contain the resolved absolute path.

The Dashboard must prefer project-owned lifecycle scripts. An adapter is allowed only when the registered project does not expose a sufficient lifecycle boundary or when an instance-specific integration is genuinely required.

## 11. Git repository status

### R10 — separation from lifecycle update (P1)

Repository status is informational. It must not create or imply a `lifecycle.update` command. The existing Update button remains available only when a safe update workflow is explicitly configured.

### R11 — bounded read-only check (P1)

`dashboard/repository_status.py` may execute only read-only Git commands against the registered target and its stored remote URL. It must not run `pull`, `fetch`, `checkout`, `switch`, `reset`, `merge`, `rebase`, package installation or hooks.

Required observations:

- whether the target is a Git worktree;
- current local commit;
- current branch or detached state;
- dirty/clean working-tree summary without file contents;
- stored remote URL and branch;
- remote branch head from a bounded `git ls-remote` call;
- last successful check time and last error reason code.

Network checks must have a short timeout, run outside the health-probe thread pool, and be cached. Default automatic interval: 15 minutes. A manual refresh may bypass freshness but must still obey single-flight and timeout rules.

### R12 — status semantics (P1)

The public service snapshot may expose:

- `not_configured` — registration has no repository metadata;
- `checking` — a bounded check is active;
- `current` — local and remote heads match;
- `update_available` — the configured remote branch has a different newer head according to available ancestry evidence;
- `ahead` — local branch contains commits not present remotely;
- `diverged` — both sides contain unique commits;
- `dirty` — working tree changes exist; this may accompany another state;
- `unavailable` — remote check timed out, failed authentication or could not resolve;
- `unknown_relation` — heads differ but safe local evidence cannot prove ancestry.

The UI must not label every unequal hash as “new version”. When ancestry cannot be established without mutating the repository, it must show “远端版本不同” rather than “有更新”. Semantic version tags may be added later but are not required for P1.

### R13 — UI presentation (P1)

The service card shows a restrained repository indicator separate from readiness and port warnings:

- no badge when tracking is not configured;
- “有更新” only for `update_available`;
- “本地领先”, “已分叉”, “有未提交修改” or “检查失败” for their exact states;
- repository URL available through a secondary details view, never occupying the primary Open action;
- no card re-creation on each cache timestamp update, preserving hover stability.

## 12. Service configuration contract

### R14 — real config is local (P0)

Tracked files contain only a synthetic `launcher.config.example.json`. The runtime loads workspace `launcher.config.json`. Service descriptors continue to store only `project_ref`; paths and Git URLs remain in registration records.

### R15 — atomic edits and backup (P0)

Any Dashboard-owned modification to configuration or registration must:

1. validate the proposed complete document;
2. acquire a workspace operation lock;
3. back up exact prior bytes;
4. write a unique temporary file on the same filesystem;
5. atomically replace the target;
6. reread and validate;
7. restore the backup on failure.

### R16 — configuration export/import (P1)

Export includes versioned service descriptors, registration identities, optional repository URLs/branches and instance adapters selected by the user. By default it excludes:

- absolute project paths;
- logs and reports;
- caches and observed commit hashes;
- secrets and environment values;
- generated GUI bundles.

An optional same-machine backup may include paths, but must be clearly labelled private and never be produced by the normal share/export command.

Import must preview additions, replacements, unresolved project paths and incompatible schema versions. It must not write until the complete bundle validates. Projects with unresolved paths remain disabled rather than being guessed or scanned.

## 13. Runtime connection

At startup the tracked runtime must:

1. resolve the local workspace;
2. require and validate its marker;
3. load the local launcher configuration;
4. resolve every `project_ref` through `project_registry.py`;
5. fail configuration validation before launching any command if references are invalid;
6. start health monitoring independently from repository-version monitoring;
7. expose only sanitized repository status to the WebUI;
8. write logs, reports and caches exclusively into the workspace.

The runtime remains bound to `127.0.0.1` and retains the per-session API token requirement.

## 14. Agent contract

The root `AGENTS.md` must state:

- this clone is the application; do not create a second Dashboard project;
- initialize only the local workspace when the marker is absent;
- never put real configuration, paths or adapters in tracked directories;
- register only explicit user-supplied project paths;
- use workspace adapters only for instance-specific glue;
- run repository privacy verification before every commit or push;
- Git-version status is read-only and does not authorize updating a project;
- framework changes and local configuration changes have different validation paths.

Initialization output must repeat the workspace location, privacy boundary and next Agent guide location.

## 15. Repository-resident Agent kit and examples

### R17 — canonical skill stays in Git (P0)

The repository must retain `SKILL.md` and its supporting `agents/` metadata as a first-class, versioned interface. A fresh Agent must be able to read the root `AGENTS.md`, follow it to `SKILL.md`, and complete initialization, explicit registration, configuration and verification without consulting the installed global skill or creating another Dashboard project.

The installed global skill may point to or be refreshed from the repository, but it must not become a second source of truth. Runtime capabilities, schema fields, `SKILL.md`, references and tests must ship in the same commit.

### R18 — reusable recipes and synthetic examples (P1)

The repository must contain a useful public library of generic examples covering common service shapes, including at least:

- static site;
- frontend development server;
- backend/API service;
- detached service with an explicit stop command;
- environment-controlled WebUI and API ports;
- application-level HTTP readiness;
- project-owned command readiness;
- structured diagnostics/log integration;
- safe update progress with single-flight locking and atomic replacement;
- optional Git repository tracking;
- an instance adapter using only `PROJECT_ROOT` and `DASHBOARD_WORKSPACE_ROOT`.

Every example must use synthetic names, temporary paths, non-secret values and isolated test ports. Examples must never contain a real project name, repository URL, command, log excerpt or user path. Optional recipes must not become default runtime dependencies or active configuration merely because they are present.

Each recipe requires:

- a short applicability statement;
- owned files and dependencies;
- copy/adoption steps that target the ignored workspace or registered project as appropriate;
- security and lifecycle assumptions;
- validation commands;
- an automated synthetic acceptance test.

### R19 — example-to-instance boundary (P0)

An Agent may read tracked examples and use them as design inputs, but must write the resulting real service descriptor and instance adapter only to the ignored workspace. No command may “customize” a tracked recipe in place. The initializer reports both locations explicitly:

- reusable guidance: repository `SKILL.md`, `references/`, `recipes/`, `examples/`;
- real instance state: resolved ignored workspace.

Repository verification must fail if a tracked recipe or example contains absolute user paths, credentials, non-synthetic registry records, runtime logs, validation reports or links to real projects.

## 16. Migration from the existing desktop instance

Migration is a separate explicit operation. It must not happen automatically during framework startup.

### Preview phase

`scripts/migrate_instance.py <existing-instance> --dry-run` inventories:

- launcher configuration;
- registered project references and targets;
- visible-name records;
- service adapters;
- entrypoints;
- logs, reports and caches;
- files that collide with the target workspace;
- runtime/UI files that must not be imported because tracked framework code owns them.

The preview prints counts and destinations without printing credentials or log bodies.

### Apply phase

The migration:

1. verifies the source instance marker;
2. creates a full target-workspace backup if the target already exists;
3. imports configuration, registrations, adapters and selected entrypoints;
4. excludes copied runtime/UI/framework files;
5. excludes caches and logs by default, with an explicit archive option;
6. converts old pointer/link records to the new registration schema;
7. validates every service reference;
8. runs configuration and privacy checks;
9. leaves the existing desktop instance unchanged;
10. writes a migration report inside workspace `reports/`.

Cutover occurs only after lifecycle and live-monitor verification. Deleting or archiving the old desktop instance requires separate user confirmation.

## 17. Security and privacy requirements

- Reject repository URLs containing embedded credentials or tokens.
- Do not expose absolute paths, full Git command output, environment values or remote authentication errors through normal service snapshots.
- Store detailed local errors only in workspace logs with bounded size and retention.
- Never execute repository hooks during status inspection.
- Do not follow registration pointers outside the explicitly registered target without validation.
- Protect workspace mutations with a cross-process lock.
- Symlink and junction handling must reject broken links and unexpected file types.
- Export must use an allowlist, never “zip the workspace”.
- The repository privacy test must use synthetic temporary fixtures only.

## 18. Verification and acceptance criteria

### P0 acceptance

1. A clean clone can be initialized and launched without creating another application directory.
2. Initialization creates only the ignored workspace and optional ignored `.env.local`.
3. Registering a synthetic project creates no tracked or untracked file outside the ignored workspace.
4. `git status --short` remains empty after initialization, registration, runtime use, adapter creation, log generation and validation.
5. A framework source edit remains visible to Git while all local instance changes remain ignored.
6. `git pull --ff-only` over a synthetic framework update preserves byte-identical workspace configuration and adapters.
7. Validator, runtime and CLI resolve the same registration through the shared module.
8. A malformed, missing or incompatible workspace fails before any service command runs.
9. Privacy verification rejects deliberately force-added registrations, paths, logs, reports and secrets.
10. macOS lifecycle and monitoring tests pass with synthetic services; Windows behavior is tested in CI and labelled untested locally.
11. A fresh clone contains the canonical skill, contracts and synthetic examples, and a no-context Agent is never instructed to generate a second Dashboard project.
12. Adopting a recipe changes only ignored workspace or explicit registered-project files; tracked recipe sources remain clean.

### P1 acceptance

1. Registering a synthetic Git project records its sanitized URL and branch only in the ignored workspace.
2. A local test remote reports `current` when heads match.
3. A newer remote commit reports `update_available` only when ancestry proves it.
4. Local-only commits report `ahead`; two-sided commits report `diverged`.
5. An unreachable remote reports `unavailable` without affecting service health.
6. Checks are cached, bounded and single-flight; one slow remote does not delay cards or health sampling.
7. No status check changes local refs, index, working tree, current branch or remote configuration.
8. The UI marks repository state without enabling Update unless a lifecycle update command exists.
9. Export/import round-trips the sanitized configuration and adapters while omitting paths, logs, caches and secrets.
10. Card hover and action state remain stable while repository-status samples update.

## 19. Required automated tests

- Workspace-path precedence and cross-platform path tests.
- Initialization dry-run, idempotency, rollback and incompatible-marker tests.
- Shared registry CRUD, replace/remove protection, symlink/junction/pointer fallback tests.
- Absolute-path and credential leakage tests.
- Config atomic-write and restore tests.
- Clean Git worktree test after complete synthetic local use.
- Framework-upgrade preservation test.
- Existing-instance migration preview/apply/rollback tests.
- Git status tests using local bare repositories only; network-independent in CI.
- Timeout and single-flight repository monitor tests.
- UI snapshot/render tests for repository badges and hover-preserving updates.
- Repository-resident skill link and cold-start instruction tests.
- Independent recipe validation using only synthetic temporary projects.
- Privacy tests that deliberately contaminate a recipe and require rejection.
- Existing lifecycle, health, port-conflict, update-progress and shutdown tests.
- macOS/Linux CI plus Windows CI for path, junction, launcher and no-console behavior.

## 20. Delivery plan

### Phase 0 — reconcile source (P0)

- Select the newest generic skill runtime as comparison input.
- Review and port generic capabilities into the Git repository.
- Do not copy desktop configuration or project-specific adapters into tracked source.
- Establish one tracked runtime source and prove parity with synthetic tests.
- Make the repository copy of `SKILL.md` and its references canonical; remove wording that depends on a separately installed skill or generated application copy.

### Phase 1 — workspace isolation (P0)

- Add workspace resolver, marker and initializer.
- Move tracked runtime to its final single-source location.
- Replace real config loading with workspace config loading.
- Add ignored workspace structure and repository privacy gate.
- Replace destination-generating instructions with in-place initialization.

### Phase 2 — shared registration (P0)

- Add `project_registry.py` and versioned records.
- Migrate validator/runtime/CLI to the shared module.
- Move adapters, entrypoints, links, logs and reports behind the workspace boundary.

### Phase 2.5 — Agent kit and recipes (P0/P1)

- Reorganize the tracked skill, references, generic recipes and synthetic examples around the in-place workspace model.
- Add no-context cold-start tests that inspect Agent instructions and prohibit a sibling-project generator workflow.
- Validate every recipe independently without writing real instance data into Git.

### Phase 3 — desktop migration (P0)

- Implement preview/apply migration.
- Run against the existing desktop instance only after synthetic tests pass.
- Validate all registrations and service descriptors without stopping unidentified active services.
- Cut over during an approved test window; preserve the old instance.

### Phase 4 — repository status (P1)

- Add sanitized Git metadata capture and local bare-repository tests.
- Add cached status monitor and API fields.
- Add restrained UI indicators and manual refresh.

### Phase 5 — export/import and closeout (P1)

- Add sanitized portable bundles and private same-machine backup distinction.
- Update README, architecture, Agent rules and verification records.
- Run privacy audit, clean-worktree gate and cross-platform CI.

## 21. Release gates

Implementation is not complete until all of the following are true:

- no second Dashboard directory is created by documented or Agent workflows;
- Public/framework code, installed skill guidance and generated Agent instructions describe the same model;
- the existing desktop instance has a validated migration preview;
- real instance data remains outside Git before and after normal use;
- the repository is clean after full local validation;
- no real service path, URL, command, log or report appears in tracked history;
- the Git repository itself contains the complete canonical skill, references and tested synthetic examples;
- a newly cloned Agent can configure an instance using only repository-resident guidance;
- macOS validation passes locally;
- Windows and Linux CI pass applicable synthetic checks;
- repository-status checks are proven non-mutating;
- the old desktop instance is retained until the user explicitly approves archival.

## 22. Product decisions fixed by this PRD

1. There will be one Dashboard application checkout, not a public clone plus generated private project.
2. Privacy comes from a versioned ignored workspace and enforcement gates, not application duplication.
3. Runtime source is tracked once and never copied into instance state.
4. User-specific configuration and scripts are local workspace data.
5. Registered projects remain external and are referenced, never copied.
6. Git status is informational and read-only; service update remains an explicit configured lifecycle action.
7. The desktop instance will be migrated non-destructively and preserved until separate confirmation.
8. The reusable skill and generic examples remain in Git; only real user instance material is ignored.
