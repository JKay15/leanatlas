# tools/dedup

This directory implements DedupGate (deduplication gate) and related report generation.

## Current status (Phase3 bootstrap)
- V0 goal: detect **hard duplicates** for **typeclass instances** only.
  - main target: duplicates caused by permuting independent binders
- Key decision: reuse the mathlib-style duplicate-declaration canonicalization approach:
  - scan declarations in the **compiled environment**
  - compute a dependency-aware binder canonicalization key
  - detect definitional aliases (avoid treating aliases as duplicate implementations)

Single source of truth plan:
- `docs/agents/execplans/phase3_dedup_gate_v0.md`

## Directory conventions
- `allowlist.json`: explicit allowed duplicates (rare; must include a reason; recommended expiry)
- (future) `scan.lean`: implementation of `lake exe leanatlas_dedup_scan` (env → DedupReport)
