---
title: Complete the remaining LOOP master-plan surfaces with parent supervision, publish/rematerialize, worktree orchestration, and standalone library routing
owner: Codex (local workspace)
status: done
created: 2026-03-08
parent_execplan: docs/agents/execplans/20260307_loop_core_parallel_nested_batch_v0.md
---

## Purpose / Big Picture
The active LOOP master plan already landed the core runtime, review orchestration, reconciliation runtime, mainline productization, and default reviewer-policy staging. The remaining gap is no longer "basic capability exists"; it is that the final batch still depends on manual handoff between waves, implicit context carry-over, LeanAtlas-only packaging/routing, and documentation that still labels those surfaces as planned or partial. This wave closes the remaining batch in one bounded implementation pass.

The target end state is:
- a parent supervisor can materialize, monitor, reroute, and close a batch of child waves
- new capabilities and human external input can be published as append-only evidence and rematerialized into downstream context packs
- review/default execution paths can consume staged preferences automatically instead of relying on manual wiring
- LeanAtlas worktree orchestration exists as a host adapter on top of LOOP core
- a reusable in-repo standalone LOOP library surface and generic skill/doc entrypoints exist for non-LeanAtlas consumers

This is a completion wave for the existing master batch, not a new product theme and not a whole-project cleanup.

## Glossary
- `parent supervisor`: a deterministic batch-level controller that owns child-wave planning, launch state, reroute/retry policy, and integrated closeout evidence.
- `child wave`: one bounded execution unit within a batch, such as a review-orchestration run, a worktree task, or a publish/rematerialize step.
- `publication event`: append-only evidence that a capability/resource/human input artifact became available for later nodes.
- `rematerialized context pack`: deterministic downstream context metadata regenerated after publication so later nodes consume explicit artifact refs instead of hidden chat memory.
- `worktree adapter`: LeanAtlas-hosted orchestration layer that maps child waves onto git worktrees without redefining LOOP core semantics.
- `standalone LOOP library`: a reusable package surface for role-neutral LOOP runtime/orchestration helpers, distinct from LeanAtlas workflow adapters.

## Scope
In scope:
- parent supervisor/autopilot runtime, artifacts, and contract surface
- publication/rematerialization runtime for bounded human external input and capability adoption
- automatic consumption of staged LOOP preferences/default execution wiring where current mainline is only partial
- LeanAtlas worktree orchestration as a host adapter
- standalone LOOP library package/docs/examples inside this repository
- generic LOOP skills and project-level skill-governance sync needed by that standalone surface
- workflow/mainline/status docs and tests required to reclassify the master-plan surfaces from planned/partial to implemented

Out of scope:
- cross-repo extraction into a different repository
- PyPI publication
- autopilot that silently edits code without an explicit child-wave plan/artifact trail
- unrelated Phase3/Phase6 backlog items outside the active LOOP master plan

Allowed directories:
- `tools/loop/**`
- `looplib/**`
- `docs/contracts/**`
- `docs/schemas/**`
- `docs/agents/**`
- `docs/setup/**`
- `docs/navigation/**`
- `docs/testing/**`
- `.agents/skills/**`
- `examples/**`
- `tests/**`
- `pyproject.toml`

Forbidden directories:
- `LeanAtlas/**`
- `Problems/**` except test overlays under `.cache/leanatlas/**`
- committing generated artifacts under `artifacts/**` except review closeout evidence

## Interfaces and Files
Primary new implementation surfaces:
- `tools/loop/batch_supervisor.py`
- `tools/loop/publication.py`
- `tools/loop/worktree_adapter.py`
- `looplib/__init__.py`
- `looplib/runtime.py`
- `looplib/review.py`
- `looplib/session.py`

Existing surfaces to upgrade:
- `tools/loop/__init__.py`
- `tools/loop/sdk.py`
- `tools/loop/user_preferences.py`
- `tools/loop/review_orchestration.py`
- `tools/loop/review_runner.py`
- `docs/contracts/LOOP_RUNTIME_CONTRACT.md`
- `docs/contracts/LOOP_GRAPH_CONTRACT.md`
- `docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md`
- `docs/contracts/LOOP_PYTHON_SDK_CONTRACT.md`
- `docs/agents/LOOP_MAINLINE.md`
- `docs/agents/STATUS.md`
- `docs/agents/MAINTAINER_WORKFLOW.md`
- `docs/agents/OPERATOR_WORKFLOW.md`
- `docs/agents/README.md`
- `docs/agents/execplans/README.md`
- `.agents/skills/README.md`
- planned child execplans under `docs/agents/execplans/20260307_batch_supervisor_autopilot_and_human_ingress_v0.md`, `20260308_loop_python_library_decoupling_packaging_v0.md`, and `20260308_loop_skills_decoupling_and_project_skills_governance_v0.md`

Primary tests:
- `tests/contract/check_loop_batch_supervisor.py`
- `tests/contract/check_loop_publication_runtime.py`
- `tests/contract/check_loop_worktree_adapter.py`
- `tests/contract/check_loop_library_packaging.py`
- `tests/contract/check_loop_mainline_docs_integration.py`
- `tests/contract/check_loop_python_sdk_contract_surface.py`
- `tests/contract/check_loop_contract_docs.py`
- `tests/contract/check_skills_standard_headers.py`
- `tests/contract/check_agents_navigation_coverage.py`
- `tests/contract/check_loop_user_preferences_policy.py`
- `tests/contract/check_loop_review_runner.py`

Registry/index updates:
- `tests/manifest.json`
- `docs/testing/TEST_MATRIX.md`
- `docs/navigation/FILE_INDEX.md`

## Milestones
### 1) Freeze the completion batch and red tests for remaining master-plan gaps
Deliverables:
- this ExecPlan as the authoritative completion wave for the remaining master-plan surfaces
- new/updated tests that fail because supervisor/publication/worktree/library/default-execution integration are still missing

Commands:
- `uv run --locked python tests/contract/check_loop_batch_supervisor.py`
- `uv run --locked python tests/contract/check_loop_publication_runtime.py`
- `uv run --locked python tests/contract/check_loop_worktree_adapter.py`
- `uv run --locked python tests/contract/check_loop_library_packaging.py`

Acceptance:
- tests fail before implementation and precisely describe the missing behaviors

### 2) Land parent supervision + publish/rematerialize runtime
Deliverables:
- deterministic parent supervisor runtime that materializes child waves, records journaled status, supports reroute/retry policy, and emits integrated closeout
- publication/rematerialization runtime that records capability and human-ingress events as append-only evidence and regenerates downstream context packs

Commands:
- `uv run --locked python tests/contract/check_loop_batch_supervisor.py`
- `uv run --locked python tests/contract/check_loop_publication_runtime.py`

Acceptance:
- parent supervision no longer depends on manual wave-to-wave handoff
- downstream adoption uses rematerialized context refs instead of hidden conversational state

### 3) Land default execution wiring + worktree adapter
Deliverables:
- review/default execution helpers automatically consume staged LOOP preferences where appropriate
- a LeanAtlas worktree adapter materializes child-wave workspaces deterministically and can be supervised as a host adapter

Commands:
- `uv run --locked python tests/contract/check_loop_worktree_adapter.py`
- `uv run --locked python tests/contract/check_loop_user_preferences_policy.py`
- `uv run --locked python tests/contract/check_loop_review_runner.py`

Acceptance:
- current mainline no longer labels default execution as manual-only
- worktree orchestration is a real adapter capability on top of LOOP core

### 4) Land standalone LOOP library + generic skills/docs routing
Deliverables:
- reusable `looplib` package surface inside the repo
- docs/examples for non-LeanAtlas consumers
- generic LOOP skills and updated skill-governance docs/index coverage

Commands:
- `uv run --locked python tests/contract/check_loop_library_packaging.py`
- `uv run --locked python tests/contract/check_skills_standard_headers.py`
- `uv run --locked python tests/contract/check_agents_navigation_coverage.py`
- `uv run --locked python tests/contract/check_loop_mainline_docs_integration.py`

Acceptance:
- non-LeanAtlas consumers have a supported import/docs/skill entrypoint
- LeanAtlas adapter skills remain explicit wrappers rather than pretending to be the generic LOOP surface

### 5) Reclassify the master plan to done and verify the integrated batch
Deliverables:
- updated contracts/docs/status/mainline matrix and child-plan closeouts
- integrated verification and fresh AI review closeout for the final state

Commands:
- `uv run --locked python tests/contract/check_loop_contract_docs.py`
- `uv run --locked python tests/contract/check_loop_python_sdk_contract_surface.py`
- `uv run --locked python tests/contract/check_loop_mainline_docs_integration.py`
- `uv run --locked python tests/contract/check_skills_standard_headers.py`
- `uv run --locked python tests/run.py --profile core`
- `uv run --locked python tests/run.py --profile nightly`
- `lake build`
- `git diff --check`

Acceptance:
- the active master plan no longer has remaining planned/partial surfaces in its own batch
- final closeout uses fresh AI review evidence for the final implementation state

## Testing plan (TDD)
New tests:
- `tests/contract/check_loop_batch_supervisor.py`
  - parent supervisor materializes child-wave journal/spec state
  - retries/reroutes are policy-bounded and journaled
  - integrated closeout consumes child-wave closeout refs and reconciliation refs
- `tests/contract/check_loop_publication_runtime.py`
  - capability publication is append-only
  - human ingress must emit explicit evidence
  - rematerialized context packs cite publications/ingress refs deterministically
- `tests/contract/check_loop_worktree_adapter.py`
  - worktree adapter creates deterministic child workspaces in a temp git repo
  - supervisor metadata can reference worktree child waves without redefining LOOP core
- `tests/contract/check_loop_library_packaging.py`
  - `looplib` imports succeed from repo root
  - standalone docs/examples use generic LOOP skills and avoid LeanAtlas-only semantics

Regression checks:
- `tests/contract/check_loop_review_runner.py`
- `tests/contract/check_loop_user_preferences_policy.py`
- `tests/contract/check_loop_contract_docs.py`
- `tests/contract/check_loop_python_sdk_contract_surface.py`
- `tests/contract/check_loop_mainline_docs_integration.py`
- `tests/contract/check_skills_standard_headers.py`
- `tests/contract/check_agents_navigation_coverage.py`

Contamination control:
- supervisor/worktree tests must use temporary git repos or `.cache/leanatlas/**`
- no test may mutate the real repo state outside temporary workspaces

## Decision log
- 2026-03-08: complete the remaining master-plan items in one implementation wave rather than prolonging the batch with more planning-only child waves.
- 2026-03-08: `publish + rematerialize + human ingress` are one runtime family and should share evidence contracts instead of separate ad hoc helpers.
- 2026-03-08: standalone LOOP reuse requires a real importable package surface and generic skills/docs, not just boundary prose.
- 2026-03-08: worktree orchestration remains a LeanAtlas adapter and should integrate through the new parent supervisor instead of redefining LOOP core.

## Rollback plan
- Revert new supervisor/publication/worktree/library files together with the related contract/doc/test changes.
- Reset mainline/status docs and child-plan states to their prior planned/partial classification if the integrated batch proves unstable.
- Verify rollback with:
  - `uv run --locked python tests/contract/check_loop_contract_docs.py`
  - `uv run --locked python tests/run.py --profile core`

## Outcomes & retrospective (fill when done)
- Completed:
  - landed parent supervision, publication/rematerialization, default review execution wiring, worktree adapter integration, standalone `looplib` packaging/docs, and generic LOOP skills
  - reclassified the remaining master-plan surfaces from planned/partial to implemented in `docs/agents/LOOP_MAINLINE.md`
  - synchronized workflow/status/README/skills/contract/test registry surfaces with the new end state
- Verification:
  - targeted LOOP completion checks:
    - `uv run --locked python tests/contract/check_loop_batch_supervisor.py`
    - `uv run --locked python tests/contract/check_loop_publication_runtime.py`
    - `uv run --locked python tests/contract/check_loop_worktree_adapter.py`
    - `uv run --locked python tests/contract/check_loop_review_automation_runtime.py`
    - `uv run --locked python tests/contract/check_loop_library_packaging.py`
    - `uv run --locked python tests/contract/check_loop_mainline_docs_integration.py`
    - `uv run --locked python tests/contract/check_loop_contract_docs.py`
    - `uv run --locked python tests/contract/check_loop_python_sdk_contract_surface.py`
    - `uv run --locked python tests/contract/check_loop_review_strategy.py`
    - `uv run --locked python tests/contract/check_loop_review_orchestration.py`
    - `uv run --locked python tests/contract/check_agents_navigation_coverage.py`
    - `uv run --locked python tests/contract/check_skills_standard_headers.py`
    - `uv run --locked python tests/contract/check_test_registry.py`
    - `uv run --locked python tests/contract/check_manifest_completeness.py`
    - `uv run --locked python tests/contract/check_test_matrix_up_to_date.py`
    - `uv run --locked python tests/contract/check_file_index_reachability.py`
    - `uv run --locked python tests/contract/check_file_index_ignores_untracked.py`
  - full verification:
    - `uv run --locked python tests/run.py --profile core`
    - `uv run --locked python tests/run.py --profile nightly`
    - `lake build`
    - `git diff --check`
- Residual risks:
  - the current completion wave lands the committed master-plan surfaces inside this repository, but future external packaging/release mechanics remain a separate topic
- Follow-on recommendation:
  - treat future LOOP expansion as follow-on bounded waves instead of reopening this completion batch
