---
title: Canonicalize generator newline behavior for FILE_INDEX and TEST_MATRIX
owner: leanatlas-maintainer
status: done
created: 2026-03-03
---

## Purpose / Big Picture
Automation verify runs are failing with `FILE_INDEX.md` and `TEST_MATRIX.md` out-of-date signals even when no semantic content has changed. Root cause is newline canonicalization drift between generator stdout, generator `--write`, and `pre-commit end-of-file-fixer`. This plan makes both generators emit a single trailing newline deterministically in both modes so checks remain stable under hooks and automation reruns.

## Scope
In scope:
- `tools/docs/generate_file_index.py`
- `tools/tests/generate_test_matrix.py`
- Regenerated outputs:
  - `docs/navigation/FILE_INDEX.md`
  - `docs/testing/TEST_MATRIX.md`

Out of scope:
- Changing file index inclusion policy
- Changing test registry semantics

## Milestones
1) Implement canonical newline output in both generators.
2) Regenerate docs and verify targeted contracts.
3) Re-run local automation wrappers for reporting/mcp sanity.

## Verification
- `./.venv/bin/python tools/docs/generate_file_index.py --write`
- `./.venv/bin/python tools/tests/generate_test_matrix.py --write`
- `./.venv/bin/python tests/contract/check_file_index_reachability.py`
- `./.venv/bin/python tests/contract/check_test_matrix_up_to_date.py`
- `./.venv/bin/python tools/coordination/run_automation_local.py --id nightly_reporting_integrity`
- `./.venv/bin/python tools/coordination/run_automation_local.py --id nightly_mcp_healthcheck`

## Outcomes & retrospective
- Implemented canonical newline normalization (`rstrip("\\n") + "\\n"`) in:
  - `tools/docs/generate_file_index.py`
  - `tools/tests/generate_test_matrix.py`
- Regenerated docs:
  - `docs/navigation/FILE_INDEX.md`
  - `docs/testing/TEST_MATRIX.md`
- Validation:
  - `./.venv/bin/python tests/contract/check_file_index_reachability.py` ✅
  - `./.venv/bin/python tests/contract/check_test_matrix_up_to_date.py` ✅
  - `./.venv/bin/python tools/coordination/run_automation_local.py --id nightly_reporting_integrity` ✅
  - `./.venv/bin/python tools/coordination/run_automation_local.py --id nightly_mcp_healthcheck` ✅
  - `./.venv/bin/python tests/run.py --profile core` ✅
