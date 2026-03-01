# Problems/AGENTS.md — Problem workspace rules (OPERATOR-focused)

This directory contains one folder per problem: `Problems/<problem_slug>/`.

## File roles (must keep clean)
- `Spec.lean`:
  - The formal statement/specification of the problem.
  - MUST NOT contain `sorry`.
  - OPERATOR mode: **never edit**. If Spec is wrong/missing assumptions → TRIAGED with evidence.

- `Proof.lean`:
  - The main proof file. MUST NOT contain `sorry`.

- `Cache.lean` / `Cache/**`:
  - Intermediate lemmas used to keep `Proof.lean` readable.
  - MUST NOT contain `sorry`.
  - For large research-grade projects, prefer `Cache/**` split by topic.

- `Scratch.lean`:
  - Allowed to contain `sorry`.
  - MUST remain isolated: nothing in `Spec/Proof/Cache` may import Scratch.

- `State.json`:
  - Machine-readable problem lifecycle state (ProblemState).
  - Must be schema-valid: `docs/schemas/ProblemState.schema.json`.
  - Updated deterministically via `python tools/problem_state/reconcile.py ...`.

## Reporting outputs
Every run MUST write reports under:
- `Problems/<problem_slug>/Reports/<run_id>/`
and must include:
- `RunReport.json` + `RunReport.md`
- `RetrievalTrace.json`
- `AttemptLog.jsonl`

Never commit `Reports/**`. Curate only selected examples under `docs/examples/`.

## OPERATOR PatchScope reminder
Allowed edits are typically limited to:
- `Proof.lean`
- `Cache.lean` / `Cache/**`
- `Scratch.lean`

Touching `Spec.lean` or anything outside the problem folder requires MAINTAINER mode.
