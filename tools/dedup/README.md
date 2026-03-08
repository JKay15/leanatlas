# tools/dedup

This directory implements DedupGate (deduplication gate) and related report generation.

## Current status (Phase3 bootstrap)
- Current V0 implementation: deterministic source-backed scan for duplicate `instance` declarations in `LeanAtlas/**`.
- Current V0 output: schema-valid `DedupReport.{json,md}` written by `tools/dedup/dedup.py`.
- Follow-on goal: replace the source-backed scan with compiled-environment scanning plus stronger canonicalization.
- When that follow-on lands, the scanner should:
  - compute dependency-aware binder canonicalization keys
  - detect definitional aliases (avoid treating aliases as duplicate implementations)

Single source of truth plan:
- `docs/agents/execplans/phase3_dedup_gate_v0.md`

## Directory conventions
- `allowlist.json`: explicit allowed duplicates (rare; must include a reason; recommended expiry)
- (future) `scan.lean`: implementation of `lake exe leanatlas_dedup_scan` (env → DedupReport)
