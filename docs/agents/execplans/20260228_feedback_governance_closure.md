# ExecPlan: Feedback Governance Closure and Verification

Date: 2026-02-28  
Mode: MAINTAINER  
Owner: Codex (local workspace)

## 1) Scope

This plan closes the remaining feedback-governance convergence work after the
new digest/ledger/traceability pipeline was added. It focuses on:

1. Wiring feedback-governance artifacts into doc-pack completeness contracts.
2. Regenerating deterministic generated docs (`TEST_MATRIX`, `FILE_INDEX`).
3. Running contract/schema/workflow validation and fixing any drift.
4. Re-checking against scaffold zip baseline and in-repo constraints.

## 2) Terms

- Feedback digest: structured extraction result from chat transcripts.
- Feedback ledger: append-only JSONL accumulation of digest items.
- Traceability matrix: derived mapping from feedback item to closure links/SLA.
- Doc-pack completeness: mandatory critical files that must always exist.

## 3) Files to change

- `tests/contract/check_doc_pack_completeness.py`
- `docs/testing/TEST_MATRIX.md` (generated)
- `docs/navigation/FILE_INDEX.md` (generated)
- `tests/manifest.json` (only if test registry drift is detected)

## 4) Milestones

### M1: Contract wiring

Deliverables:
- Update doc-pack completeness contract to include feedback governance artifacts.

Command:

```bash
./.venv/bin/python tests/contract/check_doc_pack_completeness.py
```

Acceptance:
- Returns `[docpack] OK`.

### M2: Regenerate deterministic docs

Deliverables:
- Regenerated matrix and index with current manifest/file tree.

Commands:

```bash
./.venv/bin/python tools/tests/generate_test_matrix.py --write
./.venv/bin/python tools/docs/generate_file_index.py --write
```

Acceptance:
- Both generators report write success.

### M3: Full verification for this change slice

Deliverables:
- Green contract/schema/automation checks.

Commands:

```bash
./.venv/bin/python tests/automation/validate_registry.py
./.venv/bin/python tests/contract/check_automation_closed_loops.py
./.venv/bin/python tests/contract/check_chat_feedback_filtering_policy.py
./.venv/bin/python tests/contract/check_chat_feedback_digest_policy.py
./.venv/bin/python tests/contract/check_feedback_ledger_append_only.py
./.venv/bin/python tests/contract/check_feedback_traceability_policy.py
./.venv/bin/python tests/schema/validate_schemas.py
./.venv/bin/python tests/contract/check_test_registry.py
./.venv/bin/python tests/contract/check_test_matrix_up_to_date.py
./.venv/bin/python tests/contract/check_file_index_reachability.py
./.venv/bin/python tests/run.py --profile core
```

Acceptance:
- All checks pass, or any failure is fixed and rerun to green.

## 5) Rollback points

- Doc-pack only rollback:
  - `tests/contract/check_doc_pack_completeness.py`
- Generated docs rollback:
  - `docs/testing/TEST_MATRIX.md`
  - `docs/navigation/FILE_INDEX.md`
- Feedback governance rollback:
  - Revert affected feedback scripts/contracts/tests together to maintain
    consistency (`mine_chat_feedback`, ledger, traceability, closed-loop gate).

