---
name: leanatlas-dedup
description: Run or implement LeanAtlas DedupGate. Use when you need a DedupReport (detecting bad duplicates, especially duplicate typeclass instances) to block PromotionGate or to audit duplicate policy/allowlists. Produces auditable reports.
---

## Use when
- You need to scan the compiled Lean environment for **bad duplicates** (especially duplicate typeclass instances) and produce a DedupReport.
- You are tightening/implementing DedupGate so PromotionGate can safely block promotions.

## Don't use when
- You are trying to "rename" or "move" declarations as a fix (DedupGate is a scanner; remediation happens in Promotion/GC workflows).
- You only have text-level evidence (DedupGate must be based on Lean environment facts).

## Outputs
- `.cache/leanatlas/dedup/scan/<stamp>/DedupReport.json`
- `.cache/leanatlas/dedup/scan/<stamp>/DedupReport.md`

## Must-run checks
- `uv run --locked python tools/dedup/dedup.py --repo-root . --out-root .cache/leanatlas/dedup/scan`
- `uv run --locked python tests/run.py --profile core`

# LeanAtlas DedupGate (Phase3)

This skill is for **DedupGate** work: finding duplicates that would make the library confusing or unstable.

## Hard constraints

- **Do not mutate the repo.** DedupGate is a scanner.
- **Truth source is the Lean environment.** Real DedupGate must not “guess” duplicates by text search.
- **Always write a report.** The output must include `DedupReport.json` and `DedupReport.md`.
- If you add/modify a command, artifact, or schema, update `tools/capabilities/phase3.yaml` in the same change.

## Read first (source of truth)

- `docs/contracts/DEDUP_GATE_CONTRACT.md`
- `docs/schemas/DedupReport.schema.json`
- `tools/capabilities/phase3.yaml`
- ExecPlan: `docs/agents/execplans/phase3_dedup_gate_v0.md`

## Standard workflow

1) **Run DedupGate**

```bash
uv run --locked python tools/dedup/dedup.py \
  --repo-root . \
  --out-root .cache/leanatlas/dedup/scan
```

2) **Inspect outputs**

- `.cache/leanatlas/dedup/scan/DedupReport.json`
- `.cache/leanatlas/dedup/scan/DedupReport.md`

3) **If you are implementing the real gate (Phase3+)**

- Scan the compiled Lean environment (not file text).
- Focus V0 on “hard duplicates” in **typeclass instances**.
- Produce evidence that PromotionGate can reference (path + sha256) when it blocks a promotion.
