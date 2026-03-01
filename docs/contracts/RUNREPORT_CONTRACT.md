# RUNREPORT_CONTRACT v0.3 (Phase 1 → Phase 6 upgrade)

RunReport is the canonical, machine-readable summary of a run.

## 1) Purpose
A human should be able to answer, quickly:
- What is the **main target** and where is it in the code?
- Which **stage** failed (retrieval / build / verify)?
- What are the top error **hotspots** and what should happen next?

A machine should be able to:
- validate the report schema
- aggregate categories/families
- cross-link targets ↔ diagnostics ↔ hotspots ↔ retrieval steps

## 2) Environment Stamp (anti-hallucination evidence)
**Hard rule:** `RunReport.json` MUST carry a deterministic environment stamp.

Why:
- Without it, successful runs are not reproducible.
- Postmortems become guesswork ("which tool version broke it?").

Where:
- `context.tools.environment_stamp`

Required fields (minimum):
- `lean_toolchain`:
  - meaning: contents of `lean-toolchain` (pinned Lean toolchain).
- `mathlib_rev`:
  - meaning: pinned mathlib rev from `lakefile.lean` (e.g. `v4.xx.x`).
- `pins_sha256`:
  - meaning: sha256 of `tools/deps/pins.json`.
- `pinned_tools`:
  - meaning: small map extracted from `tools/deps/pins.json` ("external wheels").

Important:
- The stamp is **runner-written** (deterministic tooling), not Codex-written.

## 3) Targets (code structure)
- `targets` MUST exist and MUST contain **exactly one** target with `role = MAIN`.
- Other targets may be `LEMMA` or `CHECK`.

Rationale:
- “Exactly one MAIN” makes reports readable and makes metrics stable.

## 4) Stages (where it failed)
`stages` is a fixed set of stage statuses:
- `retrieval`
- `build`
- `verify`

Each stage has:
- `status`: OK / FAIL / SKIPPED
- optional `refs` pointing to diagnostics/targets/trace steps

## 5) Diagnostics (single truth source for errors)
- `diagnostics` is the single truth source for compiler/tool messages.
- For TRIAGED runs:
  - diagnostics MUST contain **≥ 1 error**
  - every error diagnostic MUST include a `range` (line/col span), so humans can locate it immediately.

## 6) Hotspots (human + UI view model)
- For TRIAGED runs, `hotspots` MUST exist and have ≥ 1 item.
- Each hotspot MUST include:
  - `stage` (retrieval/build/verify)
  - `diagnostic_ids` (≥ 1)

## 7) Cross-reference model (IDs)
RunReport uses stable IDs to connect:
- `targets[].id` referenced by:
  - `triage.evidence.target_id` (optional)
  - `hotspots[].target_id` (optional)
  - `stages.*.refs.target_ids` (optional)
- `diagnostics[].id` referenced by:
  - `triage.evidence.diagnostic_ids` (required for TRIAGED)
  - `hotspots[].diagnostic_ids` (required)
  - `stages.*.refs.diagnostic_ids` (optional)
- Retrieval steps are referenced by integer indices:
  - `hotspots[].trace_step_indices`
  - `stages.*.refs.trace_step_indices`

Contract requirement:
- All referenced IDs must exist.
- IDs must be unique within their arrays.

## 8) Path convention (repo-relative POSIX)
All file paths in RunReport MUST be:
- repository-relative
- POSIX-style (`/` separators; no backslashes)
- no `..` segments

## 9) Human-readable Markdown
`RunReport.md` MUST include headings:
- `## Targets`
- `## Stages`
- `## Hotspots`
- `## Next actions`

## 10) Status-specific requirements
- SUCCESS:
  - must include `verification` and `verification.no_sorry=true`
  - must NOT include `triage`
- TRIAGED:
  - must include `triage`, `diagnostics` (≥1 error), and `hotspots` (≥1)
  - must NOT include `verification`
