# CAPABILITY_MANIFEST_CONTRACT v0

Purpose: solve a structural failure mode:
> “skills/automations cut across phases, so later phases don’t know what earlier phases actually expose.”

Solution: each Phase publishes a machine-readable manifest of its **commands / artifacts / schemas / external deps**.
Platform layers (skills/automations/evals) consume the manifest instead of guessing.

## 1) Source-of-truth locations

Each top-level phase maintains its own manifest:
- `tools/capabilities/phase3.yaml`
- `tools/capabilities/phase4.yaml`
- `tools/capabilities/phase5.yaml`

## 2) Semantics (what it is)

A Capability Manifest is an “interface table” that records:
- CLI commands exposed by the phase (e.g. `tools/gc/gc.py propose`)
- command inputs (required params/files)
- command outputs (artifact paths / filename patterns)
- schemas that outputs must validate against
- external dependencies and pins (where pinned, how to install/verify)
- minimal smoke checks (0‑LLM) that prove the tool runs end-to-end

It is not implementation detail and not marketing.
It exists for:
- Phase5: automations / skills regeneration / evals
- Maintainers: consistency audits during merges
- Phase2: registering new tools into the test matrix

## 3) Contract requirements (V0)

- Must validate against: `docs/schemas/CapabilityManifest.schema.json`
- Must be updated whenever the underlying tools change (otherwise the change is not mergeable)
- Must not be edited cross-phase without coordination (cross-phase requirements should go through an RFC/ExecPlan)

## 4) Recommended evolution (V1+)

- add `command.examples[]` (input/output examples)
- add `artifacts.retention` (which outputs are gitignored vs. archived)
- add `telemetry.signals` (bench/eval signals collected for trend tracking)
