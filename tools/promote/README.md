# tools/promote

PromotionGate (Seeds → Toolbox) entrypoint.

## Current state

- `tools/promote/promote.py` is the implemented PromotionGate entrypoint for MAINTAINER
  runs (12 gates, structured evidence, report outputs).
- The implementation:
  - reads a `PromotionPlan.json`
  - writes `PromotionReport.json` + `PromotionReport.md`
  - evaluates migration/dependency/soundness gates and emits gate-by-gate evidence
  - validates required supporting commands when available
  - does **not** mutate the repo

Current implementation covers the V0 gates described in:
- `docs/contracts/PROMOTION_GATE_CONTRACT.md`

## CLI

### Smoke / Run

Run from repo root:

```bash
uv run --locked python tools/promote/promote.py \
  --repo-root . \
  --plan tools/promote/fixtures/plan_minimal.json \
  --out-root .cache/leanatlas/promotion/gate \
  --mode MAINTAINER
```

Outputs:
- `.cache/leanatlas/promotion/gate/PromotionReport.json`
- `.cache/leanatlas/promotion/gate/PromotionReport.md`

## Design constraints (do not "downgrade")

When implementing the real gate:

- Structural signals must be computed via Lean/mathlib tooling (no heuristic fallbacks).
- If required tooling is missing or the command errors, the gate must **fail** and attach
  auditable evidence (stdout/stderr + sha256), rather than skipping.
