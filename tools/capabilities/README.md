# tools/capabilities/

This directory stores per-phase **Capability Manifests**.
They exist to decouple phases and prevent “later phases guessing what earlier phases expose”.

- Phase3/4/5 declare which commands/artifacts/schemas/dependencies they provide.
- Phase5 (platform layer) can generate/validate skills, automations, bench/evals from these manifests.
- During merges, maintainers can run consistency audits across phases.

Source-of-truth contract:
- `docs/contracts/CAPABILITY_MANIFEST_CONTRACT.md`

Schema:
- `docs/schemas/CapabilityManifest.schema.json`
