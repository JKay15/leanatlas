# tools/AGENTS.md — Tooling rules (deterministic, auditable)

`tools/**` contains deterministic scripts used by the workflow:
- patch scope checking
- budgets / judge logic
- indexing / retrieval (future)
- reporting generation

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
