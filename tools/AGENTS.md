# tools/AGENTS.md — Tooling rules (deterministic, auditable)

`tools/**` contains deterministic scripts used by the workflow:
- patch scope checking
- budgets / judge logic
- indexing / retrieval (future)
- reporting generation
- automation execution wrappers (`tools/coordination/run_automation.py`, `run_automation_local.py`)
- automation stuck-run recovery (`tools/coordination/recover_stuck_automation_runs.py`)
- LOOP runtime core (`tools/loop/**`): execution state model, run-key materialization, append-only evidence store
- formalization deterministic core (`tools/formalization/**`): ledger upgrade adapters, worklist/apply flow, anti-cheat, strong validation

## Non-negotiables
- No network access.
- Deterministic outputs for deterministic inputs.
- Every new output format must have:
  - a JSON schema under `docs/schemas/`
  - a contract doc under `docs/contracts/`
  - positive + negative fixtures under `tests/schema/fixtures/`
  - core-tier tests validating it.

## Where to write outputs
- Never write into the repository except under `artifacts/**` or `.cache/leanatlas/**`.
- Do not write into `Problems/**` directly unless the workflow contract requires it.
