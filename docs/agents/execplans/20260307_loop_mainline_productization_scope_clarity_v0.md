---
title: Clarify that LOOP is the primary subject of mainline productization and project-level integration
owner: Codex (local workspace)
status: done
created: 2026-03-07
---

## Purpose / Big Picture
Recent batch planning correctly moved native parallel/nested execution into LOOP core, but the follow-on theme `docs/skills productization + mainline integration` is still easy to misread as a generic whole-project documentation sweep. That is not the intent. The intent is that LOOP has already become a central mainline system in LeanAtlas, and the next productization wave should make that reality legible and usable. This plan tightens the wording so the primary subject is explicit: LOOP mainline productization comes first; LeanAtlas project-level workflow/docs/skills/index updates are supporting integration work that align the repository with that reality. The plan also adds a small contract-style doc guard so later edits cannot silently reintroduce the same ambiguity.

## Glossary
- LOOP mainline productization: turning already-landed LOOP capabilities into the canonical, documented, skill-backed default path in LeanAtlas mainline.
- Project-level integration: updating LeanAtlas-wide workflow docs, status pages, skills, and indices so they accurately reflect LOOP's mainline role.
- Experimental asset classification: deciding whether a `.cache/leanatlas/tmp/**` asset is already absorbed into mainline, retained only as evidence/fixture input, or still experimental-only.

## Scope
In scope:
- tighten the active master plan wording so the docs/skills/mainline wave is explicitly LOOP-first
- add one planned child ExecPlan that captures the intended `LOOP-as-mainline + project-level integration` scope
- add/update a deterministic contract test guarding the clarified wording
- update manifest/matrix/index entries required by the new test and plan

Out of scope:
- implementing the actual docs/skills productization wave
- closing the separate maintainer closeout-ref blocker
- broad project documentation cleanup unrelated to LOOP mainline integration

Allowed directories:
- `docs/agents/execplans/**`
- `tests/contract/**`
- `tests/manifest.json`
- `docs/testing/**`
- `docs/navigation/**`

Forbidden directories:
- `tools/**`
- `docs/contracts/**`
- `.cache/**`
- unrelated project docs outside the files listed below

## Interfaces and Files
Primary files:
- `docs/agents/execplans/20260307_loop_core_parallel_nested_batch_v0.md`
- `docs/agents/execplans/20260307_loop_mainline_productization_scope_clarity_v0.md`
- new planned child plan under `docs/agents/execplans/`
- new contract-style doc guard under `tests/contract/`

Registry/index files:
- `tests/manifest.json`
- `docs/testing/TEST_MATRIX.md`
- `docs/navigation/FILE_INDEX.md`

## Milestones
### 1) TDD guard for wording drift
Deliverables:
- add a failing doc-guard test that requires the master plan to describe the productization wave as LOOP-first, not a generic project sweep

Commands:
- `uv run --locked python tests/contract/check_loop_mainline_productization_scope.py`

Acceptance:
- the new test fails before the master plan wording is updated

### 2) Clarify master-plan wording and stage the explicit child plan
Deliverables:
- update the master plan wording
- add a planned child plan for the actual docs/skills/mainline integration implementation

Commands:
- `sed -n '1,260p' docs/agents/execplans/20260307_loop_core_parallel_nested_batch_v0.md`
- `sed -n '1,260p' docs/agents/execplans/20260307_loop_mainline_productization_integration_v0.md`

Acceptance:
- the master plan explicitly says LOOP is the primary subject of the wave
- the child plan explicitly scopes project-level integration as support for LOOP mainline adoption

### 3) Register and verify
Deliverables:
- manifest/matrix/index updates for the new guard
- required verification and FAST-only review evidence

Commands:
- `uv run --locked python tests/contract/check_loop_mainline_productization_scope.py`
- `uv run --locked python tests/run.py --profile core`
- `uv run --locked python tests/run.py --profile nightly`
- `lake build`

Acceptance:
- the new guard passes
- required verification completes without introducing new LOOP/doc regressions

## Testing plan (TDD)
New test:
- `tests/contract/check_loop_mainline_productization_scope.py`
  - master plan must frame the productization/integration wave as LOOP-first
  - master plan must reject treating the wave as a generic whole-project docs sweep
  - the planned child plan must exist and explicitly describe project-level integration as supporting LOOP mainline adoption

Regression:
- manifest/matrix/index stay synchronized

## Decision log
- Prefer a narrow wording fix plus deterministic guard over hand-wavy interpretation in chat.
- Keep the actual productization implementation as a separate planned child plan; this plan only clarifies batch authority and prevents ambiguity.

## Rollback plan
- Revert:
  - this ExecPlan
  - the child plan
  - the new doc guard test
  - manifest/matrix/index updates
  - the master plan wording edits
- Verify rollback with:
  - `uv run --locked python tests/contract/check_test_registry.py`

## Outcomes & retrospective (fill when done)
- Completed:
  - clarified the active master batch plan so the later docs/skills/mainline wave is explicitly `LOOP-first`
  - added the planned child plan `docs/agents/execplans/20260307_loop_mainline_productization_integration_v0.md`
  - added the deterministic guard `tests/contract/check_loop_mainline_productization_scope.py`
  - updated the execplan index, test registry, test matrix, and tracked-file navigation index
- Verification:
  - `uv run --locked python tests/contract/check_loop_mainline_productization_scope.py`
  - `uv run --locked python tests/contract/check_execplan_readme_authority.py`
  - `uv run --locked python tests/contract/check_test_registry.py`
  - `uv run --locked python tests/contract/check_test_matrix_up_to_date.py`
  - `uv run --locked python tests/contract/check_file_index_reachability.py`
  - `uv run --locked python tests/contract/check_english_only_policy.py`
  - `uv run --locked python tests/run.py --profile core`
  - `uv run --locked python tests/run.py --profile nightly`
  - `lake build`
  - `git diff --check`
  - FAST AI review closeout: `artifacts/reviews/20260307_loop_mainline_productization_scope_clarity_review_round2_fast_response.md`
- Residual risks:
  - the actual `LOOP mainline productization + LeanAtlas project-level integration` implementation has not started yet; this plan only removed authority ambiguity and staged the child implementation plan
  - one earlier materialized maintainer session became stale after the ExecPlan bytes changed; final closeout was re-materialized on a fresh run key
- Follow-on recommendation:
  - close the outstanding `20260307_maintainer_closeout_ref_v0` blocker tail
  - then start the planned child wave `20260307_loop_mainline_productization_integration_v0.md`
