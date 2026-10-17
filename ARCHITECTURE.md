# Architecture

Local Service Dashboard uses one tracked application checkout and one private local workspace. Privacy is a storage boundary, not a second generated project.

```text
repository (tracked)                 local workspace (ignored)
├─ dashboard/ runtime + WebUI        ├─ workspace.json
├─ scripts/ tools and verification   ├─ launcher.config.json
├─ defaults/ public empty defaults   ├─ registry/projects/*.json
├─ references/ contracts             ├─ projects/ links or pointers
├─ recipes/ reusable patterns        ├─ adapters/ and entrypoints/
├─ examples/ synthetic fixtures      ├─ logs/ reports/ cache/
└─ SKILL.md Agent workflow           └─ backups/ imports/
                 │
                 └── explicit registration ──> external service projects
```

The workspace defaults to `.local-dashboard/`. `LOCAL_SERVICE_DASHBOARD_DATA_DIR` may select an absolute path or a path relative to the repository. `dashboard/workspace.py` is the single resolver used by initialization, registration, validation, runtime, migration, and bundles.

`workspace.json` and project registration records are versioned documents. A missing, malformed, foreign, or incompatible marker fails before any service command runs. Dashboard-owned JSON writes use same-filesystem temporary files and atomic replacement. Bundle import and legacy migration create backups before replacement.

`dashboard/project_registry.py` owns path resolution and optional repository metadata. Service descriptors contain a `project_ref`, never a real path. Visible links are convenience only; the versioned record is authoritative.

Runtime health and Git repository status are independent:

- health decides whether the service can be used;
- URL decides what Open launches;
- `ports` reports declared endpoint roles and collisions;
- lifecycle update executes only an explicitly configured project workflow;
- repository status performs bounded, cached, non-mutating comparison and may report current, newer remote, ahead, diverged, different, or unavailable.

The browser UI is an authenticated localhost control surface, not a general process supervisor. It does not scan ports, infer projects, auto-restart services, or kill unknown listeners.

Portable export is allowlisted: sanitized configuration, registration identities, optional repository coordinates, and explicitly selected adapters. It excludes targets, environment values, logs, reports, cache, observed revisions, and framework code. Import is preview-first, requires explicit project path mappings, validates in a temporary workspace, backs up current state, and rolls back on failure.
