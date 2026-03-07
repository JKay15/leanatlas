---
title: Implement LOOP core native parallel+nested execution and stage the next adapter batch
owner: Codex (local workspace)
status: active
created: 2026-03-07
---

## Purpose / Big Picture
The current LOOP implementation already exposes graph-level `PARALLEL` and `NESTED` composition in contracts and the Python SDK, but runtime execution is still effectively serial and nested execution is not yet a first-class runtime/evidence capability. That gap makes it too easy to over-explain LOOP as if worktree orchestration or maintainer review automation were the core of parallelism, when those are only LeanAtlas-specific adapters. This batch corrects that layering. First, it upgrades LOOP core so native parallel execution and nested-loop lineage are real runtime features with deterministic evidence. Then it stages the next review/worktree/operator integrations on top of that core. The result should be: a role-neutral LOOP core that supports real concurrent branch execution and explicit nested child-loop evidence, plus a clear follow-on path for review orchestration, worktree orchestration, workflow integration, and LOOP mainline productization.

Clarification for the later docs/skills/mainline wave:
- LOOP mainline productization is the primary subject of that wave.
- LeanAtlas project-level integration is supporting work: update status/workflow docs, skills, and indices so they reflect LOOP's mainline role.
- That later wave is not a generic whole-project documentation sweep.
- `.cache/leanatlas/tmp/**` experimental assets must be classified, not wholesale copied into mainline.

Batch-level end-state requirement (hard target for the full staged batch, not only the first wave):
- after all staged follow-on themes are completed, LOOP must be able to automatically advance an approved batch from parent ExecPlan freeze through child-wave execution and final integrated closeout, rather than requiring a human to manually hand off every wave
- after all staged follow-on themes are completed, LOOP must be able to accept bounded human-provided external information during execution, publish it as append-only evidence, rematerialize downstream context, and continue execution without relying on hidden conversational state

## Glossary
- LOOP core: role-neutral runtime/scheduler/evidence layer under `tools/loop/**`.
- Adapter: LeanAtlas-specific workflow layer built on top of LOOP core, such as maintainer review automation, worktree orchestration, or OPERATOR problem workflows.
- Native parallel execution: runtime actually executes dependency-free nodes concurrently, not merely accepts `PARALLEL` edges in the graph schema.
- Nested lineage: explicit persisted evidence linking a child/nested node execution to its parent predecessors and graph context.
- Capability publish: append-only publication that a new feature/doc/skill/resource version is now available for later nodes.
- Context rematerialize: explicit regeneration of a child session/context pack so later AI nodes can consume newly published resources.

## Scope
In scope:
- LOOP core runtime and graph evidence for native parallel execution and nested lineage.
- Contract/schema/doc updates required to make the above auditable and non-misleading.
- Deterministic contract tests for:
  - real parallel execution vs serial fallback
  - nested lineage evidence
  - graph/dataflow semantics gaps exposed by the new runtime behavior
- Recording the next-batch adapter roadmap in one authoritative master plan.

Follow-on items staged by this plan but not all implemented in the first wave:
- batch supervisor/autopilot (parent-loop orchestration across child waves)
- review orchestration automation (pyramid reviewer + staged narrowing + supersession/reconciliation)
- user-configurable LOOP defaults and post-onboarding preference presets
- default reviewer policy realignment to `FAST + low`
- capability publish + context refresh
- human external input ingress + rematerialization
- independent LOOP Python library extraction, packaging, and non-LeanAtlas usage docs
- LOOP skills decoupling plus LeanAtlas project-level skills governance/completeness
- LeanAtlas worktree orchestration
- OPERATOR/MAINTAINER workflow integration
- graph/dataflow/live smoke expansion
- LOOP mainline productization plus LeanAtlas project-level integration and bounded decoupling

Out of scope for the first implementation wave:
- full autonomous multi-worktree overnight execution
- replacing every existing maintainer path with nested child Codex workers immediately
- cross-repo extraction of LOOP into a separate repository

Allowed directories:
- `tools/loop/**`
- `docs/contracts/**`
- `docs/schemas/**` (only if schema changes are required)
- `docs/agents/execplans/**`
- `docs/testing/**`
- `docs/navigation/**`
- `tests/**`
- `.agents/skills/**` (only if a new skill/update is directly required by the implemented milestone)

Forbidden directories:
- `LeanAtlas/**`
- `Problems/**` (except temporary test overlays under `.cache/leanatlas/**`)
- `.cache/leanatlas/tmp/**` experiment assets as primary implementation location

## Interfaces and Files
Primary implementation files:
- `tools/loop/graph_runtime.py`
- `tools/loop/sdk.py`
- `tools/loop/__init__.py`
- `docs/contracts/LOOP_GRAPH_CONTRACT.md`
- `docs/contracts/LOOP_RUNTIME_CONTRACT.md`
- `docs/contracts/LOOP_PYTHON_SDK_CONTRACT.md`
- `docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md`
- `docs/schemas/LoopGraphSpec.schema.json` (if runtime needs schema clarification)

Primary tests:
- `tests/contract/check_loop_graph_merge_semantics.py`
- `tests/contract/check_loop_composition_presets.py`
- `tests/contract/check_loop_python_sdk_contract_surface.py`
- `tests/contract/check_loop_contract_docs.py`
- `tests/contract/check_loop_wave_execution_policy.py`
- `tests/contract/check_loop_schema_validity.py`
- new first-wave tests under `tests/contract/check_loop_graph_parallel_nested_runtime.py`

Generated/registry files:
- `tests/manifest.json`
- `docs/testing/TEST_MATRIX.md`
- `docs/navigation/FILE_INDEX.md`

## Milestones
### 1) Freeze corrected batch authority and first-wave acceptance
Deliverables:
- This master ExecPlan becomes the only active authoritative plan for the batch.
- Record the layer split:
  - LOOP core: native parallel + nested + resource arbitration
  - LeanAtlas adapters: review orchestration, worktree orchestration, workflow integration

Commands:
- `sed -n '1,220p' docs/agents/execplans/20260307_loop_core_parallel_nested_batch_v0.md`

Acceptance:
- The active plan is self-contained and no longer treats worktree orchestration as the definition of LOOP parallelism.

### 2) TDD first: native parallel runtime + nested lineage
Deliverables:
- Add/adjust deterministic contract tests for:
  - real concurrent execution when `scheduler.max_parallel_branches > 1`
  - serial fallback when `max_parallel_branches = 1`
  - nested-lineage evidence for `NESTED` edges

Commands:
- `uv run --locked python tests/contract/check_loop_graph_parallel_nested_runtime.py`
- `uv run --locked python tests/contract/check_loop_graph_merge_semantics.py`

Acceptance:
- Tests fail before implementation and pass after implementation.
- The tests distinguish graph semantics from real runtime concurrency.

### 3) Implement LOOP core native parallel + nested runtime evidence
Deliverables:
- Upgrade `LoopGraphRuntime` to actually execute dependency-free nodes concurrently, bounded by `scheduler.max_parallel_branches`.
- Persist explicit nested-lineage evidence for `NESTED` edges.
- Keep deterministic GraphSummary/arbitration ordering and resource-arbiter assumptions intact.

Commands:
- `uv run --locked python tests/contract/check_loop_graph_parallel_nested_runtime.py`
- `uv run --locked python tests/contract/check_loop_composition_presets.py`

Acceptance:
- Parallel runtime is no longer only a contract claim.
- Nested execution is no longer only a surface-level edge kind; runtime emits explicit nested evidence.

### 4) Align contracts/docs/schema with the corrected layering
Deliverables:
- Update LOOP docs to clarify:
  - graph semantics vs real concurrent execution
  - LOOP core vs LeanAtlas adapter responsibilities
  - nested execution evidence expectations
- Update schema/SDK docs only if implementation requires it.

Commands:
- `uv run --locked python tests/contract/check_loop_contract_docs.py`
- `uv run --locked python tests/contract/check_loop_python_sdk_contract_surface.py`
- `uv run --locked python tests/contract/check_loop_schema_validity.py`

Acceptance:
- Contracts no longer imply that maintainer/worktree concerns define native LOOP parallelism.

### 5) Stage the follow-on adapter work on top of the new core
Deliverables:
- Record the ordered follow-on themes in this plan:
  - batch supervisor/autopilot
  - review orchestration automation
  - user-configurable LOOP defaults and post-onboarding preference presets
  - default reviewer policy realignment to `FAST + low`
  - capability publish + context refresh
  - human external input ingress + rematerialization
  - independent LOOP Python library extraction, packaging, and non-LeanAtlas usage docs
  - LOOP skills decoupling plus LeanAtlas project-level skills governance/completeness
  - LeanAtlas worktree orchestration
  - OPERATOR/MAINTAINER workflow integration
  - graph/dataflow/live smoke expansion
  - LOOP mainline productization + LeanAtlas project-level integration + bounded decoupling
- Point the final theme at an explicit child plan so later implementation cannot drift into a generic project-wide documentation cleanup.
  - child plan: `docs/agents/execplans/20260307_loop_mainline_productization_integration_v0.md`
  - child plan: `docs/agents/execplans/20260308_loop_user_preferences_and_onboarding_defaults_v0.md`
  - child plan: `docs/agents/execplans/20260308_review_default_profile_policy_v0.md`
  - child plan: `docs/agents/execplans/20260308_loop_python_library_decoupling_packaging_v0.md`
  - child plan: `docs/agents/execplans/20260308_loop_skills_decoupling_and_project_skills_governance_v0.md`

Commands:
- `sed -n '1,260p' docs/agents/execplans/20260307_loop_core_parallel_nested_batch_v0.md`

Acceptance:
- The batch has one authoritative plan and a clear implementation order after the first-wave core lands.
- The staged docs/skills/mainline wave is explicitly LOOP-first rather than a generic project sweep.

### 6) Verification and closeout
Deliverables:
- Run required LOOP/maintainer verification and update outcomes.

Commands:
- `uv run --locked python tests/contract/check_loop_graph_parallel_nested_runtime.py`
- `uv run --locked python tests/contract/check_loop_contract_docs.py`
- `uv run --locked python tests/contract/check_loop_schema_validity.py`
- `uv run --locked python tests/contract/check_loop_wave_execution_policy.py`
- `uv run --locked python tests/contract/check_loop_python_sdk_contract_surface.py`
- `uv run --locked python tests/contract/check_skills_standard_headers.py`
- `uv run --locked python tests/run.py --profile core`
- `uv run --locked python tests/run.py --profile nightly`
- `lake build`

Acceptance:
- The first-wave core lands with passing verification.
- Maintainer LOOP closeout uses fresh review evidence for the final implementation state.

## Testing plan (TDD)
New first-wave tests:
- `tests/contract/check_loop_graph_parallel_nested_runtime.py`
  - proves real runtime concurrency when configured
  - proves serial fallback when configured
  - proves nested-lineage evidence is emitted

Regression checks to rerun:
- `tests/contract/check_loop_graph_merge_semantics.py`
- `tests/contract/check_loop_composition_presets.py`
- `tests/contract/check_loop_contract_docs.py`
- `tests/contract/check_loop_python_sdk_contract_surface.py`
- `tests/contract/check_loop_wave_execution_policy.py`
- `tests/contract/check_loop_schema_validity.py`

Contamination control:
- all runtime/evidence tests must write only under temporary directories or `artifacts/loop_runtime/by_key/<run_key>/...`
- no test may mutate real worktree content outside the test repo/temp root

## Decision log
- Corrected the earlier planning mistake: native LOOP parallelism is a core concern, not a worktree-only adapter concern.
- `OPERATOR` and `MAINTAINER` remain LeanAtlas workflow semantics and must not define LOOP core APIs.
- Worktree orchestration remains important, but it is explicitly staged after core parallel/nested runtime lands.
- Nested LOOP is treated as a first-class runtime/evidence topic rather than a dormant SDK surface.
- Full-batch automation is not considered delivered until a parent-loop supervisor/autopilot can materialize child waves, reconcile their evidence, and close out on the latest integrated state.
- Human-provided external information must enter through explicit ingress/publish/rematerialize/adopt flow; implicit mid-run chat-state drift is forbidden.
- The docs/skills/mainline-integration theme is defined as `LOOP-as-mainline` productization first, with project-level integration updates only insofar as they make LOOP usable as a LeanAtlas mainline system.
- Bounded decoupling inside LeanAtlas docs is not sufficient by itself; if LOOP is expected to become reusable across Codex projects, that extraction/packaging path must remain a first-class follow-on theme in this master batch.
- The same applies to skills: reusable LOOP capabilities cannot remain discoverable only through `leanatlas-*` skills, and project-level skills completeness cannot stay an implicit side effect of code/docs work.

## Rollback plan
- Revert the new core-parallel/nested runtime changes and first-wave tests/docs:
  - `tools/loop/graph_runtime.py`
  - any associated schema/doc updates
  - `tests/contract/check_loop_graph_parallel_nested_runtime.py`
  - manifest/matrix/index updates
- Verify rollback with:
  - `uv run --locked python tests/contract/check_loop_graph_merge_semantics.py`
  - `uv run --locked python tests/run.py --profile core`

## Outcomes & retrospective (fill when done)
- Completed:
  - first-wave core runtime parallel+nested execution landed earlier in this batch
  - follow-on child plans for LOOP mainline productization, user preferences, Python-library decoupling, and skills governance are now all materialized
  - LOOP mainline productization and user-preference staging are now completed child waves
- Verification:
- Residual risks:
- Follow-on recommendation:
