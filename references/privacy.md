# Skill and project privacy isolation

Treat the installed Skill as read-only generic tooling. Treat each materialized launcher as private project state.

## Allowed locations

| Data | Allowed location |
|---|---|
| Generic runtime, schema, UI, synthetic example | Skill package |
| Real project path or registration | Explicit launcher instance only |
| Real service name, port, lifecycle command, env binding | Instance `dashboard/launcher.config.json` only |
| Project-specific adapter | Instance `dashboard/adapters/<service-id>/` only |
| Optional platform GUI launcher | Instance `dashboard/entrypoints/` only |
| Runtime logs and state history | Instance `dashboard/logs/` and browser memory only |
| Lifecycle validation report | Instance `dashboard/validation-report.json` only |
| Readable project shortcut | Instance `projects/` only |

## Prohibited writes

Never add real project data to Skill frontmatter, instructions, references, UI metadata, template defaults, scripts, tests, examples, fixtures, or bundled assets. Never replace the generic template registration with a real symlink or absolute pointer. Never use a real project log as a Skill test fixture.

## Required materialization

Create an instance only with:

```bash
python scripts/create_launcher.py <explicit-destination>
```

The script copies only generic framework files and creates `dashboard/.launcher-instance` in the destination. The generic template has no marker. Its registrar and normal runtime execution refuse to operate there, preventing accidental project registration inside the Skill. Keep internal state inside `dashboard`, project links inside `projects`, and the installed Skill pointer at `launcher-skill`; expose only English-named folders, launch files, and concise Markdown documentation at the instance root.

## Generic improvement rule

If a real project exposes a missing capability, describe the capability generically, build a synthetic fixture under a temporary directory, change the framework against that fixture, and run the privacy audit. Do not preserve the original path, project name, command, port, configuration contents, log excerpt, or repository identity.

## Audit

Run `python scripts/audit_privacy.py`. It rejects symlinks, absolute project pointers, user-home paths, runtime reports, and log files inside the Skill package.
