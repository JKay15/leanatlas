# REPORTING_CONTRACT v0.4 (Phase 2 → Phase 6 evidence upgrade)

This contract freezes **where** run artifacts live and **what** files are required.

## 1) Where reports live
- Non-committed runs:
  - `Problems/<problem_slug>/Reports/<run_id>/...`  (gitignored)
- Committed stable examples:
  - `docs/examples/reports/<run_id>/...`

## 2) Required files per run directory
A run directory MUST contain:
- `RunReport.json`       (machine-readable; schema: `docs/schemas/RunReport.schema.json`)
- `RunReport.md`         (human-readable; minimum headings required)
- `RetrievalTrace.json`  (machine-readable; schema: `docs/schemas/RetrievalTrace.schema.json`)
- `AttemptLog.jsonl`     (machine-readable; each line validates against `docs/schemas/AttemptLogLine.schema.json`)

Optional:
- `Artifacts/` (patches/diffs/extra outputs)
- `Cmd/` (runner-captured command stdout/stderr logs)
- `pins_used.json` (AgentEval sidecar: dependency pin fingerprint; runner-generated in AgentEval `--mode run`)
- `Formalization/` (formalization gate/governor decisions, when formalization workflow is enabled)

Evidence-chain rule (Phase6+):
- If `AttemptLog.jsonl` contains `exec_spans[*].stdout_path/stderr_path`, then those paths MUST exist within the run directory.
- `Cmd/` is the recommended location.

Rationale:
- Phase 6 requires audit-grade evidence. JSON summaries are not enough; we need the command outputs.

Formalization extension:
- When dual-gate formalization workflow runs, governor outputs should be archived as machine-readable JSON
  under `Formalization/` (or an equivalent deterministic path referenced by run artifacts).

## 3) run_id rules
- `run_id` is the folder name.
- `RunReport.json:run_id` MUST equal folder name exactly.
- Regex: `^[A-Za-z0-9._-]+$`

## 4) No bloat policy
- `Problems/**/Reports/**` is ignored by git.
- Only curated, minimal examples belong in `docs/examples/`.
