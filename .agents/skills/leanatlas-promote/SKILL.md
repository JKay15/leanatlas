---
name: leanatlas-promote
description: Run or implement LeanAtlas PromotionGate (Seeds→Toolbox). Use when producing PromotionPlan/PromotionReport, enforcing Rule-of-Three reuse evidence, and generating auditable structural signals (min_imports, import-graph, directoryDependency). MAINTAINER-only.
---

## Use when
- You are in **MAINTAINER** mode and need to promote Incubator Seeds into `LeanAtlas/Toolbox/**` under PromotionGate rules.
- You are implementing or tightening PromotionGate checks (structural signals, reuse evidence, dedup constraints).

## Don't use when
- You are in **OPERATOR** mode or working on a single `Problems/<slug>/` proof (promotion is forbidden there).
- You cannot run the pinned Lean/mathlib toolchain (PromotionGate relies on real structural evidence, not guesses).

## Outputs
- `.cache/leanatlas/promotion/gate/<stamp>/PromotionReport.json`
- `.cache/leanatlas/promotion/gate/<stamp>/PromotionReport.md`
- (optional) `.cache/leanatlas/promotion/gate/<stamp>/evidence/**` (import-graph / dirDep / logs)

## Must-run checks
- `uv run --locked python tools/promote/promote.py --repo-root . --plan <PromotionPlan.json> --out-root .cache/leanatlas/promotion/gate --mode MAINTAINER`
- `uv run --locked python tests/run.py --profile core`

# LeanAtlas PromotionGate (Phase3)

This skill is for **PromotionGate** work: turning Incubator *Seeds* into Toolbox tools **safely**.

## Hard constraints

- **MAINTAINER only.** If you are in OPERATOR mode, do not attempt promotion.
- **No silent weakening.** Do not replace Lean/mathlib structural checks with heuristics or “best effort” fallbacks.
- **Always leave an audit trail.** PromotionReport must include every required gate and non-empty evidence.
- If you add/modify a command, artifact, or schema, update `tools/capabilities/phase3.yaml` in the same change.
- Any new rule must be recorded in `docs/coordination/DECISIONS.md`.

## Read first (source of truth)

- `docs/contracts/PROMOTION_GATE_CONTRACT.md`
- `docs/schemas/PromotionPlan.schema.json`
- `docs/schemas/PromotionReport.schema.json`
- `tools/capabilities/phase3.yaml`
- ExecPlan: `docs/agents/execplans/phase3_promotion_structural_signals_v1.md`

## Standard workflow

1) **Prepare a PromotionPlan** (`PromotionPlan.json`)
   - List candidates (decl names) and where they come from.
   - Include reuse evidence (distinct `problem_slug` count) and migration intent (alias/compat).

2) **Run PromotionGate**

```bash
uv run --locked python tools/promote/promote.py \
  --repo-root . \
  --plan <PromotionPlan.json> \
  --out-root .cache/leanatlas/promotion/gate \
  --mode MAINTAINER
```

3) **Inspect outputs**
   - `.cache/leanatlas/promotion/gate/PromotionReport.json`
   - `.cache/leanatlas/promotion/gate/PromotionReport.md`

4) **If gates fail**
   - Fix the plan or implement the missing gate logic.
   - Re-run the same command.
   - Keep outputs deterministic: same inputs → same report (aside from timestamps).
