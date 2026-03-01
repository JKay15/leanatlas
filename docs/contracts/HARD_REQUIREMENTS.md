# LeanAtlas hard requirements (non‑negotiables)

This document lists requirements that **must not drift**. If a change conflicts with any item here, the correct outcome is **TRIAGED** with evidence.

## Truth and verification
- The **Lean environment** (a successful `lake build` with the pinned toolchain) is the only authority.
- Anything “retrieved” from external tools (search/MCP) is only a **candidate** until verified locally.

## Workflow discipline
- The small loop may exit only as **SUCCESS** or **TRIAGED**.
- OPERATOR mode may only edit within a single `Problems/<slug>/` directory (PatchScope).
- Any attempt/run must write the reporting triple:
  - `RunReport.json` (+ `RunReport.md`)
  - `RetrievalTrace.json`
  - `AttemptLog.jsonl`

## Evidence chain (anti-hallucination)
- Command execution evidence must be captured by the runner (not by the agent):
  - full argv, cwd, exit_code, duration_ms
  - stdout/stderr paths and/or sha256
- `RunReport` must include an **Environment Stamp** (Lean toolchain + mathlib rev + pins hash).

## Test-driven development (TDD)
- Every phase must have robust tests. “It seems fine” is not acceptable.
- Tests must include:
  - deterministic contract checks (schemas/layout/refs)
  - end-to-end workflow tests (proof loop, gates, scenarios)
  - **sequence** and **pressure** scenarios (interleaving, regression, soak)

## External dependencies (supply chain)
- Any external tool/library must be **version-pinned** (see `tools/deps/pins.json`).
- Docs must state **exact install commands** and a **smoke check** to verify the install.
- The repo uses **uv** (not `requirements.txt`).

## Library growth (Dedup / Promotion / GC)
- Promotion must be gated by dedup + reuse evidence + rollbackability.
- Seeds must be searchable and importable on demand.
- GC is driven by **domain/session signals**, not by wall-clock time.

## Domain-driven retrieval
- MSC2020 (plus local extensions) is used to prune/expand retrieval.
- Domain metadata must be carried in plans/reports so behavior is auditable.
