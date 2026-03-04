---
title: Make FILE_INDEX generation depend on git-tracked files only
owner: Codex (MAINTAINER)
status: done
created: 2026-03-04
---

## Purpose / Big Picture
`generated-doc-guardrails` failed in GitHub while local checks passed because `docs/navigation/FILE_INDEX.md` was generated from local disk state, not repository state. A local untracked file (`AGENTS.override.md`) was included in the committed index, but CI checkout did not have it, so contract verification failed. This plan removes that nondeterminism by making file indexing use git-tracked files as the canonical source. We also add a dedicated contract test to prevent regressions where untracked files leak into FILE_INDEX. After this change, both human and Codex contributors get identical FILE_INDEX results across local and CI environments.

## Glossary
- Git-tracked file: path returned by `git ls-files` for the repository worktree.
- Untracked file: local file present on disk but not tracked by git.
- FILE_INDEX contract: `tests/contract/check_file_index_reachability.py` exact-match check between generated output and committed `docs/navigation/FILE_INDEX.md`.

## Scope
In scope:
- `tools/docs/generate_file_index.py`
- new contract test under `tests/contract/`
- `tests/manifest.json`
- regenerated `docs/navigation/FILE_INDEX.md` and `docs/testing/TEST_MATRIX.md`
- this ExecPlan and ExecPlan README index

Out of scope:
- automation scheduler behavior
- TEST_MATRIX generator semantics
- changes outside generated-doc consistency

## Interfaces and Files
- `tools/docs/generate_file_index.py`: source-of-truth file enumeration and markdown render.
- `tests/contract/check_file_index_ignores_untracked.py` (new): regression test for untracked-file contamination.
- `tests/manifest.json`: register new contract test in core profile.
- `docs/navigation/FILE_INDEX.md`: regenerated from updated generator.
- `docs/testing/TEST_MATRIX.md`: regenerated after manifest update.

## Milestones
1) Reproduce + codify failure (TDD)
- Deliverables: new contract test + manifest entry.
- Commands:
  - `./.venv/bin/python tests/contract/check_file_index_ignores_untracked.py`
- Acceptance:
  - Fails before generator fix when temp untracked file appears in generated stdout.

2) Implement tracked-only enumeration
- Deliverables: update `tools/docs/generate_file_index.py` to enumerate via git index (with deterministic ordering and existing exclude policy).
- Commands:
  - `./.venv/bin/python tests/contract/check_file_index_ignores_untracked.py`
  - `./.venv/bin/python tests/contract/check_file_index_reachability.py`
- Acceptance:
  - New test passes.
  - Reachability contract passes locally.

3) Regenerate generated docs + full verification
- Deliverables: regenerated `docs/navigation/FILE_INDEX.md`, `docs/testing/TEST_MATRIX.md`, plan status set to done.
- Commands:
  - `./.venv/bin/python tools/docs/generate_file_index.py --write`
  - `./.venv/bin/python tools/tests/generate_test_matrix.py --write`
  - `./.venv/bin/python tests/run.py --profile core`
  - `./.venv/bin/python tests/run.py --profile nightly`
  - `lake build`
- Acceptance:
  - Core + nightly pass (allowed skips only for env-gated tests).
  - `lake build` passes.
  - `git status --porcelain` clean except intentional edits.

## Testing plan (TDD)
- Add `tests/contract/check_file_index_ignores_untracked.py`.
- Scenario:
  - Create a deterministic temporary untracked file under repo root.
  - Run FILE_INDEX generator in stdout mode.
  - Assert temporary file path is absent from output.
  - Cleanup file in finally block.
- Register in `tests/manifest.json` with `profile=core`.

## Decision log
- Decision: canonical enumeration uses `git ls-files` rather than recursive filesystem scan.
  - Reason: CI and local must match repository snapshot, not local workstation state.
  - Rejected: expanding exclusion list for local files (fragile and incomplete).

## Rollback plan
- Revert generator and new test+manifest entry.
- Regenerate FILE_INDEX and TEST_MATRIX.
- Re-run:
  - `./.venv/bin/python tests/contract/check_file_index_reachability.py`
  - `./.venv/bin/python tests/contract/check_test_matrix_up_to_date.py`

## Outcomes & retrospective (fill when done)
- Implemented tracked-only FILE_INDEX generation and added regression contract.
- Aligned generator with subprocess-wrapper policy by using `tools.workflow.run_cmd`.
- Updated AGENTS navigation link for `.agents/skills/docs/` and regenerated env/doc indexes.
- Verified:
  - `./.venv/bin/python tests/run.py --profile core`
  - `./.venv/bin/python tests/run.py --profile nightly`
  - `lake build`
