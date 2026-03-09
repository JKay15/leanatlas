---
title: Phase 1 owner-boundary delta for LOOP repo split: extract generic preference policy into looplib
owner: Codex (local workspace)
status: done
created: 2026-03-09
parent_execplan: docs/agents/execplans/20260309_loop_external_repo_split_v0.md
---

## Purpose / Big Picture
This is the first bounded implementation delta under phase 1 of the external repo split plan. The parent plan says `looplib` cannot remain a thin facade over `tools/loop/**`; phase 1 must start turning reusable behavior into library-owned implementation while leaving LeanAtlas-specific persistence and workflow adapters behind. The smallest high-value seam is `tools/loop/user_preferences.py`, because it currently mixes reusable review-policy defaults with LeanAtlas-local artifact path semantics.

This delta extracts the generic preference/policy model into `looplib`, reduces `tools.loop.user_preferences` to a LeanAtlas adapter wrapper around that generic model, and adds an ownership-boundary contract test. It does not complete the entire phase-1 owner inversion; it establishes the first real boundary and a repeatable test pattern for later phase-1 deltas.

## Glossary
- generic preference policy model: the reusable constants, normalization helpers, and default-review policy builders that do not depend on LeanAtlas artifact roots.
- LeanAtlas persistence adapter: path selection and file I/O bound to `.cache/leanatlas/onboarding/loop_preferences.json` and repo-root semantics.
- owner-boundary test: a contract test that proves `looplib` owns a reusable implementation surface instead of merely re-exporting `tools.loop`.

## Scope
In scope:
- add a library-owned preference/policy module under `looplib/**`
- refactor `tools/loop/user_preferences.py` so LeanAtlas persistence calls into the library-owned policy model
- add one new contract test that pins the owner-boundary for this seam
- update test/docs registries required for the new contract test

Out of scope:
- moving all reusable LOOP modules out of `tools/loop/**`
- changing external repo extraction mechanics
- changing review policy semantics or onboarding defaults
- changing worktree, maintainer, or review orchestration ownership in this delta

Allowed files:
- `looplib/**`
- `tools/loop/user_preferences.py`
- `tests/contract/check_loop_library_ownership_boundary.py`
- `tests/contract/check_loop_user_preferences_policy.py`
- `tests/manifest.json`
- `docs/testing/TEST_MATRIX.md`
- `docs/navigation/FILE_INDEX.md`
- this ExecPlan

Forbidden files:
- `tools/loop/maintainer.py`
- `tools/loop/worktree_adapter.py`
- `tools/loop/review_orchestration.py`
- `docs/contracts/**` unless the implementation forces a contract-text correction
- any phase-2/phase-3 extraction path

## Interfaces and Files
- `looplib/preferences.py`
  - new generic owner for review preset/policy constants and normalization/build helpers
- `looplib/review.py`
  - should source generic policy helpers from `looplib.preferences`, not from `tools.loop`
- `looplib/__init__.py`
  - may re-export the generic preference-policy helper if needed by existing standalone surface expectations
- `tools/loop/user_preferences.py`
  - keeps LeanAtlas artifact path, load/write/ensure semantics, but delegates generic policy logic to `looplib.preferences`
- `tests/contract/check_loop_library_ownership_boundary.py`
  - proves the generic preference model is looplib-owned and free of LeanAtlas persistence coupling
- `tests/contract/check_loop_user_preferences_policy.py`
  - remains the behavioral regression test for the committed preference path and defaults

## Milestones
### 1) Freeze the owner-boundary test first
Deliverables:
- add `tests/contract/check_loop_library_ownership_boundary.py`
- register the new test in manifest/navigation/test matrix

Commands:
- `uv run --locked python tests/contract/check_loop_library_ownership_boundary.py`

Acceptance:
- the new test fails against the pre-change state because the generic preference model is not yet library-owned

### 2) Extract the generic preference policy model into looplib
Deliverables:
- add `looplib/preferences.py`
- refactor `tools/loop/user_preferences.py`
- update `looplib/review.py` / `looplib/__init__.py` imports if needed

Commands:
- `uv run --locked python tests/contract/check_loop_library_ownership_boundary.py`
- `uv run --locked python tests/contract/check_loop_user_preferences_policy.py`
- `uv run --locked python tests/contract/check_loop_library_packaging.py`

Acceptance:
- `looplib.preferences` owns the reusable policy/default builders
- `tools.loop.user_preferences` retains LeanAtlas path/persistence semantics without duplicating policy logic
- standalone `looplib` imports no longer need `tools.loop` for the extracted preference-policy behavior

### 3) Close the bounded delta cleanly
Deliverables:
- verified phase-1 delta with maintainer LOOP evidence and AI review closeout

Commands:
- `uv run --locked python tests/contract/check_loop_library_ownership_boundary.py`
- `uv run --locked python tests/contract/check_loop_user_preferences_policy.py`
- `uv run --locked python tests/contract/check_loop_library_packaging.py`
- `uv run --locked python tests/run.py --profile core`
- `uv run --locked python tests/run.py --profile nightly`
- `lake build`
- `git diff --check`

Acceptance:
- this bounded delta closes without expanding into phase 2 or phase 3
- later phase-1 deltas can reuse the same owner-boundary pattern on other reusable seams

## Testing plan (TDD)
Add first:
- `tests/contract/check_loop_library_ownership_boundary.py`
  - asserts `looplib.preferences` exists
  - asserts it does not embed the LeanAtlas artifact path constant
  - asserts `looplib.review` sources `build_default_review_policy` from `looplib.preferences`
  - asserts `tools.loop.user_preferences` remains the owner of LeanAtlas artifact-path persistence

Regression coverage:
- `tests/contract/check_loop_user_preferences_policy.py`
- `tests/contract/check_loop_library_packaging.py`

Contamination control:
- no temporary workspaces
- no writes outside temporary dirs created by existing tests

## Decision log
- 2026-03-09: start phase 1 with `user_preferences` because it is explicitly called out by the parent plan and is the smallest seam that mixes generic policy with LeanAtlas-local persistence.
- 2026-03-09: do not attempt full repo-wide owner inversion in the first delta; establish one enforced boundary and reuse the pattern.

## Rollback plan
- remove `looplib/preferences.py`
- inline delegated policy helpers back into `tools/loop/user_preferences.py`
- remove `tests/contract/check_loop_library_ownership_boundary.py`
- remove the registry/index entries for that test

Rollback verification:
- `uv run --locked python tests/contract/check_loop_user_preferences_policy.py`
- `uv run --locked python tests/contract/check_loop_library_packaging.py`

## Outcomes & retrospective (fill when done)
- Completed:
  - added `looplib/preferences.py` as the first library-owned policy/defaults module under the repo-split phase-1 program
  - refactored `tools/loop/user_preferences.py` so LeanAtlas persistence/path handling remains local while reusable defaults/runtime resolution live in `looplib.preferences`
  - switched `looplib.review` to source `build_default_review_policy` from `looplib.preferences`
  - replaced eager `looplib` top-level imports with lazy export resolution so the new module can be imported without package-init circular failures
  - added `tests/contract/check_loop_library_ownership_boundary.py` and registered it in `tests/manifest.json` / `docs/testing/TEST_MATRIX.md`
  - hardened the ownership-boundary test after reviewer stall evidence exposed that the initial import probe only blocked the exact `tools.loop.user_preferences` name and did not pin the root `looplib` re-export path
- Verification:
  - targeted:
    - `uv run --locked python tests/contract/check_loop_library_ownership_boundary.py`
    - `uv run --locked python tests/contract/check_loop_user_preferences_policy.py`
    - `uv run --locked python tests/contract/check_loop_library_packaging.py`
    - `uv run --locked python tests/contract/check_manifest_completeness.py`
    - `uv run --locked python tests/contract/check_test_matrix_up_to_date.py`
    - `uv run --locked python tests/contract/check_loop_contract_docs.py`
    - `uv run --locked python tests/contract/check_loop_python_sdk_contract_surface.py`
    - `uv run --locked python tests/contract/check_loop_schema_validity.py`
    - `uv run --locked python tests/contract/check_loop_wave_execution_policy.py`
    - `uv run --locked python tests/contract/check_skills_standard_headers.py`
  - broad:
    - `uv run --locked python tests/run.py --profile core`
    - `uv run --locked python tests/run.py --profile nightly`
    - `lake build`
    - `git diff --check`
  - AI review closeout:
    - attempted twice via `codex exec review`, but no terminal response artifact was produced before the first run stalled and the second run was invalidated by a real follow-up test hardening
    - attempts evidence: `artifacts/reviews/20260309_loop_external_repo_split_phase1_owner_boundary_review_attempts.md`
- Residual risks:
  - this delta only moves the preference-policy seam; the rest of the generic LOOP surfaces still live behind `tools/loop/**` and need later phase-1 deltas
  - no clean fresh AI review response exists for the final byte state of this child delta because reviewer tooling stalled before emitting a terminal response
- Follow-on recommendation:
  - next phase-1 delta should move another reusable seam out of `tools/loop/**`, likely starting with review/runtime helper ownership while preserving LeanAtlas-specific adapters in place
