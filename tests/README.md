# LeanAtlas tests/

Run:
- Core:   `python tests/run.py --profile core`
- Nightly:`python tests/run.py --profile nightly`
- Soak:   `python tests/run.py --profile soak`

## What core covers (PR gate)
Core is intentionally **fast + deterministic** and does **not** require Codex.

It includes:
- Schema validation (+/- fixtures)
- Canonical JSON determinism
- Report layout + reference integrity
- PatchScope policy + Judge determinism
- E2E case/scenario *spec validation* (YAML/JSON structure validation)
- Doc-pack completeness (critical docs not forgotten)
- Automations spec validation + dry-runs (for `status=active` core automations)

See the authoritative list in `tests/manifest.json`.

## What nightly may cover
Nightly is allowed to be heavier and may require additional local setup:
- Executable E2E scenarios (Lean + mathlib)
- Performance/import budget checks
- MCP compatibility/health checks
- Dedup/Promotion/GC scans

Nightly still must be deterministic given the same environment.

## What soak covers
Soak is intentionally "extreme" and is allowed to be slow.

It is meant to surface:
- state leaks across sequential runs
- flakiness and regression chains
- brittle automation assumptions

Soak is expected to run only in developer machines or dedicated CI runners.
