# TESTING_CONTRACT v0.4

This contract makes TDD enforceable.

## Single source of truth: Test Registry

- **Registry (authoritative):** `tests/manifest.json` (version=2)
- **Human matrix (derived):** `docs/testing/TEST_MATRIX.md`

Rules:

1) Every test script (by convention) MUST be registered in `tests/manifest.json`.
   - Enforced by: `python tests/contract/check_test_registry.py`

2) The matrix MUST be kept in sync with the registry.
   - Regenerate: `python tools/tests/generate_test_matrix.py --write`
   - Enforced by: `python tests/contract/check_test_matrix_up_to_date.py`

3) Tests are tiered:
   - `core`: PR gate (fast + deterministic)
   - `nightly`: heavier checks (may require external tools)
   - `soak`: extreme sequential/stress execution

## Core (PR gate)
Core MUST include:

1) Schema contract tests
   - `python tests/schema/validate_schemas.py`
   - Positive fixtures must validate; negative fixtures must fail.

2) AGENTS size contract
   - `python tests/contract/check_agents_size.py`
   - Every committed `AGENTS*.md` < 32KiB.

3) Report layout contract
   - `python tests/contract/check_reports_layout.py`
   - Validates `docs/examples/reports/<run_id>/...` contains all required files.

4) AttemptLog.jsonl contract
   - `python tests/contract/check_attemptlog_jsonl.py`
   - Every example run must include `AttemptLog.jsonl`; each line must validate.

5) RunReport reference integrity
   - `python tests/contract/check_runreport_refs.py`
   - Ensures IDs and cross-references are consistent.

6) RunReport markdown structure
   - `python tests/contract/check_runreport_md.py`
   - Ensures minimum headings exist (`Targets`, `Stages`, `Hotspots`, `Next actions`).

7) RetrievalTrace invariants
   - `python tests/contract/check_retrievaltrace_invariants.py`
   - Contiguous steps, budget consistency.

8) Canonical JSON formatting
   - `python tests/determinism/check_canonical_json.py`
   - Prevents noisy diffs and non-deterministic formatting.

9) Doc-pack completeness
   - `python tests/contract/check_doc_pack_completeness.py`
   - Ensures critical cross-cutting docs (MCP/Automations) are not forgotten.

10) Automation registry + dry-runs
   - `python tests/automation/validate_registry.py`
   - `python tests/automation/run_dry_runs.py`
   - Validates automation specs and executes dry-runs for active core automations.


## Rules for changes
- Schema change ⇒ bump `schema_version` + update fixtures (positive + negative).
- Bug fix ⇒ add regression fixture.
- Generated run outputs MUST NOT be committed under `Problems/**/Reports/**`.

## Nightly (Phase 2+)
Nightly may include:
- E2E golden runs (deterministic patch sequences)
- Performance/import budget checks
- External tool compatibility checks

## Soak / stress (Phase 2+)
Soak may include:
- Long sequential E2E scenarios
- Repeated runs to detect leaks/flakiness
- Automation behavior under repeated failures

## 6. E2E case validation (Phase 2)
- Command: `python tests/e2e/validate_cases.py`
- Purpose: validate `tests/e2e/golden/*/case.yaml` against schema and enforce coverage matrix (deterministic).
