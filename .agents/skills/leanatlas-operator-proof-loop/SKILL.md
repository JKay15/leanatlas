---
name: leanatlas-operator-proof-loop
description: Solve ONE problem in OPERATOR mode by running the LeanAtlas small loop. Produce RunReport/RetrievalTrace/AttemptLog as evidence. Do not modify system directories.
---

## Use when
- You are in **OPERATOR** mode and must solve exactly one `Problems/<problem_slug>/` to **SUCCESS** (or produce a high-quality **TRIAGED** exit).
- You must generate the standard evidence artifacts (RunReport / RetrievalTrace / AttemptLog).

## Don't use when
- The task requires editing `LeanAtlas/**`, `tools/**`, `docs/contracts/**`, `.github/**`, or multiple problems (switch to MAINTAINER + ExecPlan).
- You are missing a local Lean/Lake environment and cannot run `lake build` (you can still draft, but you cannot claim SUCCESS).

## Outputs
- `Problems/<slug>/Reports/<run_id>/RunReport.json`
- `Problems/<slug>/Reports/<run_id>/RunReport.md`
- `Problems/<slug>/Reports/<run_id>/RetrievalTrace.json`
- `Problems/<slug>/Reports/<run_id>/AttemptLog.jsonl`

## Must-run checks
- `lake build Problems.<slug>.Proof`
- `python tools/problem_state/reconcile.py --problem <slug> --run-report Problems/<slug>/Reports/<run_id>/RunReport.json`

## Inputs
- `problem_slug`: directory name under `Problems/` (e.g. `am_gm_ineq_2026_01`)
- `budgets.limits`: optional overrides (max_attempts/max_steps/max_external_queries/max_wall_time_ms)

## Hard constraints (OPERATOR)
- Allowed edits: `Problems/<slug>/Proof.lean`, `Problems/<slug>/Cache.lean`, `Problems/<slug>/Cache/**/*.lean`, `Problems/<slug>/Scratch.lean`
- Forbidden: `Problems/<slug>/Spec.lean`, `LeanAtlas/**`, `tools/**`, `docs/contracts/**`, `.github/**`, any other problem directory.
- Scratch may contain `sorry`, but must never be imported by Spec/Proof/Cache.

## Procedure (must follow order)
Read: `docs/agents/OPERATOR_WORKFLOW.md` and `docs/contracts/WORKFLOW_CONTRACT.md`.

1) Mode check
- Confirm OPERATOR (no root `AGENTS.override.md`).
- If MAINTAINER is detected, stop and ask for explicit instruction (do not assume).

2) Intake and target identification
- Open `Problems/<slug>/Spec.lean` and identify the MAIN target decl name.
- Open `Problems/<slug>/Proof.lean` and current state.
- Use `Scratch.lean` for experiments if needed.

3) Start a run
- Choose a `run_id` and create `Problems/<slug>/Reports/<run_id>/`.
- Initialize budgets and counters (write Attempt 0 snapshot line).

4) Snapshot
- Record file hashes for Proof/Cache/**/Scratch/Spec.
- Record current imports summary.

5) Retrieval ladder (record every step in RetrievalTrace)
- Try environment-local actions first (LSP code actions / local search).
- Then Toolbox/Seeds if available; otherwise Mathlib.
- External search is last; every external candidate must be validated locally.

6) Attempt (one bounded change)
- Make the smallest change that could advance.
- Build the smallest target possible (prefer module-level build over full build).
- Extract diagnostics (file/range/message/severity). Update RunReport.diagnostics and reference ids.

7) Decide (Judge)
- SUCCESS if build OK and verify OK and no-sorry.
- TRIAGED if any of:
  - scope violation (forbidden touched files)
  - tooling failure
  - budget exhausted
  - stagnation exceeded K
  - missing assumptions / definition mismatch / statement false (escalate)
- Otherwise CONTINUE to next attempt.

8) Reporting (mandatory on every exit)
- Populate RunReport (targets, stages, diagnostics, hotspots, triage/verification).
- Ensure all references are valid (diagnostic_ids exist, etc.).
- Keep repo clean: never commit Reports/artifacts.

## Notes
- The Advisor (Codex reasoning) may propose hypotheses/next actions, but the Judge decision must be deterministic and evidenced.
