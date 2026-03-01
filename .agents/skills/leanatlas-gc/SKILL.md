---
name: leanatlas-gc
description: Run or implement LeanAtlas GCGate. Use when producing GCPlan/GCReport, applying a GCPlan to update tools/index/gc_state.json, or testing the Phase3 GC loop (reachability + quarantine/archival).
---

## Use when
- You need to run the Seeds GC loop (propose/apply) and update `tools/index/gc_state.json` under the Phase3 contract.
- You are implementing or strengthening GCGate reachability/domain/session-count logic and need GCPlan/GCReport evidence.

## Don't use when
- You are solving a single problem proof in OPERATOR mode (use `leanatlas-operator-proof-loop`).
- You intend to move/rename `.lean` files inside Seeds in V0 (forbidden; V0 modifies metadata only).

## Outputs
- `.cache/leanatlas/gc/propose/<stamp>/GCPlan.json`
- `.cache/leanatlas/gc/propose/<stamp>/GCReport.json` + `GCReport.md`
- `.cache/leanatlas/gc/apply/<stamp>/GCReport.json` + `GCReport.md`
- `tools/index/gc_state.json` (the only file apply is allowed to mutate in V0)

## Must-run checks
- `uv run --locked python tools/gc/gc.py propose --repo-root . --out-root .cache/leanatlas/gc/propose --mode OPERATOR`
- `uv run --locked python tools/gc/gc.py apply --repo-root . --plan .cache/leanatlas/gc/propose/GCPlan.json --out-root .cache/leanatlas/gc/apply --mode MAINTAINER`

# LeanAtlas GCGate (Phase3)

This skill is for **GC (garbage collection) of Seeds**: deciding which Incubator items stay active, get quarantined, or get archived.

## Hard constraints

- `propose` must **not** modify the repo. It only writes a plan + report.
- `apply` is **MAINTAINER only** and must only mutate `tools/index/gc_state.json` (V0 rule).
- Always leave an audit trail: write `GCPlan.json` + `GCReport.json` + `GCReport.md`.
- If you add/modify a command, artifact, or schema, update `tools/capabilities/phase3.yaml` in the same change.

## Read first (source of truth)

- `docs/contracts/GC_GATE_CONTRACT.md`
- `docs/contracts/GC_STATE_CONTRACT.md`
- `docs/schemas/GCPlan.schema.json`
- `docs/schemas/GCReport.schema.json`
- `docs/schemas/GCState.schema.json`
- `tools/capabilities/phase3.yaml`
- ExecPlan: `docs/agents/execplans/phase3_gc_gate_v0.md`

## Standard workflow

1) **Propose a GC plan** (safe; allowed in OPERATOR or MAINTAINER)

```bash
uv run --locked python tools/gc/gc.py propose \
  --repo-root . \
  --out-root .cache/leanatlas/gc/propose \
  --mode OPERATOR
```

Outputs:
- `.cache/leanatlas/gc/propose/GCPlan.json`
- `.cache/leanatlas/gc/propose/GCReport.json`
- `.cache/leanatlas/gc/propose/GCReport.md`

2) **Apply the plan** (writes only `tools/index/gc_state.json`; MAINTAINER only)

```bash
uv run --locked python tools/gc/gc.py apply \
  --repo-root . \
  --plan .cache/leanatlas/gc/propose/GCPlan.json \
  --out-root .cache/leanatlas/gc/apply \
  --mode MAINTAINER
```

3) **Inspect outputs**

- `.cache/leanatlas/gc/apply/GCReport.json`
- `.cache/leanatlas/gc/apply/GCReport.md`
- `tools/index/gc_state.json` (the only mutated file)
