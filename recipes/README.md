# Optional recipes

Recipes are version-matched, generic integration guidance. Adopting a recipe must write real descriptors and instance-specific adapters only to the ignored local workspace or to the explicitly registered project. A recipe is never enabled automatically.

Every future recipe must declare its applicability, owned files, dependencies, security assumptions and validation command, and must include a synthetic acceptance test.

- [safe update progress](safe-update-progress.md) covers transactional lifecycle updates.
- `examples/service-shapes.json` covers common service, health, URL, port, diagnostics, and registration shapes.
