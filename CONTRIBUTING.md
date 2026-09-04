# Contributing

Contributions should preserve the dashboard's narrow scope: explicit local services, manual controls, localhost access, observable health, and no automatic restart.

Before opening a pull request:

1. Read `AGENTS.md` and the relevant contracts in `references/`.
2. Use only synthetic service fixtures and placeholder paths, ports, and commands.
3. Update the runtime, validator, schema/reference documentation, and tests together when adding configuration behavior.
4. Run the repository checks listed in `README.md`.
5. Describe which operating systems were actually tested.

Do not submit generated dashboard instances, real registrations, logs, screenshots containing local data, validation reports, credentials, or personal filesystem paths.
