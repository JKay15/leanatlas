---
title: Split reusable LOOP code and generic skills into separate repositories while keeping LeanAtlas as a first-party host
owner: Codex (local workspace)
status: active
created: 2026-03-09
parent_execplan: docs/agents/execplans/20260308_loop_master_plan_completion_wave_v0.md
---

## Purpose / Big Picture
The current repository has already completed the in-repo decoupling wave: `looplib/**` exists as a reusable import surface, generic `loop-*` skills exist, and LeanAtlas-specific adapters/workflows are documented separately. That is enough for in-repo reuse, but it is not yet the same as physical separation into standalone repositories that other users can consume directly. Today the reusable Python surface is still a facade over `tools/loop/**`, the generic skills still live under LeanAtlas's `.agents/skills/**`, and LeanAtlas remains both the implementation host and the distribution point.

This plan stages the next bounded step: a three-phase repository split that turns the current boundary into real external ownership. The target end state is: one standalone LOOP Python library repository, one standalone generic LOOP skills repository, and LeanAtlas as a first-party host/adaptor that consumes both through pinned versions. The split must not be a big-bang rewrite; it must preserve deterministic contracts, stable migration shims, and cross-repo verification at every phase.

## Glossary
- owner inversion: changing the authoritative implementation owner from LeanAtlas-local `tools/loop/**` to the reusable `looplib` package surface before physical extraction.
- looplib repo: the future standalone repository that owns reusable LOOP Python code, generic contracts/schemas/examples, and library-facing documentation. Recommended slug at implementation kickoff: `codex-looplib`.
- loop-skills repo: the future standalone repository that owns generic `loop-*` skills and their versioned routing/compatibility metadata. Recommended slug at implementation kickoff: `codex-loop-skills`.
- LeanAtlas host adapter: any workflow/runtime/document surface that remains specific to LeanAtlas and should not move into the standalone library/skills repositories.
- compatibility shim: a temporary wrapper kept in LeanAtlas so existing callers keep working while imports/docs migrate to external ownership.
- cross-repo smoke: a deterministic integration check proving LeanAtlas can run against a pinned local checkout or installed version of `looplib` and the generic skills repository.

## Scope
In scope:
- freeze the target repository boundaries for:
  - standalone reusable LOOP Python code/docs/contracts/examples
  - standalone generic LOOP skills
  - LeanAtlas-retained host adapters and workflow docs
- plan the three implementation phases needed to reach those boundaries safely
- define compatibility rules, migration shims, version pinning, and cross-repo verification
- define the TDD matrix required before any extraction or repo cutover lands

Out of scope:
- implementing the split in this planning turn
- changing reviewer policy, onboarding defaults, or formalization behavior beyond what the split requires
- introducing new LOOP product features unrelated to separation
- publishing to PyPI during the first extraction wave unless the plan's acceptance criteria for that phase are explicitly updated
- rewriting LeanAtlas-specific workflow semantics to look generic when they are not

Allowed directories for the future implementation wave:
- `looplib/**`
- `tools/loop/**`
- `docs/contracts/**`
- `docs/schemas/**`
- `docs/setup/**`
- `docs/agents/**`
- `docs/testing/**`
- `docs/navigation/**`
- `.agents/skills/**`
- `examples/**`
- `tests/**`
- `pyproject.toml`
- `uv.lock`
- `artifacts/loop_runtime/**` for required maintainer LOOP graph/session/closeout evidence
- `.cache/leanatlas/tmp/loop_repo_split/**` for temporary multi-repo integration workspaces only

Forbidden directories for the future implementation wave:
- `LeanAtlas/**`
- `Problems/**` except temporary overlays under `.cache/leanatlas/tmp/**`
- broad unrelated Phase3/Phase6 changes
- committing generated extraction workspaces or release tarballs into this repository
- using `artifacts/loop_runtime/**` for anything other than required maintainer evidence and stable closeout aliases

## Target repository boundary
### Future `looplib` repository
Must own:
- reusable LOOP runtime/composition/evidence code
- reusable review planning/orchestration/reconciliation code
- reusable publication/rematerialization code
- generic contracts and schemas for those surfaces
- standalone quickstart docs and examples
- library-owned tests for generic behavior

Candidate owners to move out of LeanAtlas:
- `tools/loop/assurance.py`
- `tools/loop/batch_supervisor.py`
- `tools/loop/dirty_tree_gate.py`
- `tools/loop/errors.py`
- `tools/loop/graph_runtime.py`
- `tools/loop/model.py`
- `tools/loop/publication.py`
- `tools/loop/resource_arbiter.py`
- `tools/loop/review_canonical.py`
- `tools/loop/review_history.py`
- `tools/loop/review_orchestration.py`
- `tools/loop/review_prompting.py`
- `tools/loop/review_reconciliation.py`
- `tools/loop/review_runner.py`
- `tools/loop/review_strategy.py`
- `tools/loop/run_key.py`
- `tools/loop/runtime.py`
- `tools/loop/sdk.py`
- `tools/loop/store.py`
- `tools/loop/wave_gate.py`
- `looplib/**`
- `docs/contracts/LOOP_RUNTIME_CONTRACT.md`
- `docs/contracts/LOOP_GRAPH_CONTRACT.md`
- `docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md`
- `docs/contracts/LOOP_PYTHON_SDK_CONTRACT.md`
- `docs/schemas/Loop*.json`
- `docs/schemas/CanonicalReviewResult.schema.json`
- `docs/schemas/InstructionResolutionReport.schema.json`
- `docs/schemas/ResourceLease.schema.json`
- `docs/schemas/ReviewSupersessionReconciliation.schema.json`
- `docs/schemas/WaveExecutionLoopRun.schema.json`
- `docs/setup/LOOP_LIBRARY_QUICKSTART.md`
- `examples/looplib_quickstart.py`

Needs explicit phase-1 split/refactor before extraction:
- `tools/loop/user_preferences.py`
  - split into generic policy/preset model vs LeanAtlas persistence path/state adapter
- `tools/loop/__init__.py`
  - convert from monolithic host export surface into compatibility wrappers over library-owned modules

### Future `loop-skills` repository
Must own:
- generic `loop-mainline`
- generic `loop-review-orchestration`
- generic `loop-batch-supervisor`
- generic `loop-review-reconciliation`
- a versioned compatibility matrix describing which `looplib` versions they target
- standalone installation/use docs for non-LeanAtlas users

### LeanAtlas retained surfaces
Must remain in LeanAtlas:
- `tools/loop/maintainer.py`
- `tools/loop/worktree_adapter.py`
- LeanAtlas-specific workflow entry docs:
  - `docs/agents/MAINTAINER_WORKFLOW.md`
  - `docs/agents/OPERATOR_WORKFLOW.md`
  - `docs/agents/LOOP_MAINLINE.md`
  - `docs/agents/README.md`
  - `docs/agents/STATUS.md`
- LeanAtlas wrapper skills:
  - `.agents/skills/leanatlas-loop-mainline/SKILL.md`
  - `.agents/skills/leanatlas-loop-maintainer-ops/SKILL.md`
  - `.agents/skills/leanatlas-loop-review-acceleration/SKILL.md`
- LeanAtlas-specific artifact-root, AGENTS-chain, onboarding, and formalization wiring

Files that must not move until renamed or semantically clarified:
- `MaintainerLoopSession`
  - either rename/make role-neutral before moving into `looplib`, or keep it LeanAtlas-local if maintainer semantics remain host-specific

## Interfaces and Files
Current authoritative references that must stay aligned during the split:
- `.agents/skills/README.md`
- `docs/agents/LOOP_MAINLINE.md`
- `docs/agents/MAINTAINER_WORKFLOW.md`
- `docs/agents/OPERATOR_WORKFLOW.md`
- `docs/agents/README.md`
- `docs/agents/STATUS.md`
- `docs/setup/LOOP_LIBRARY_QUICKSTART.md`
- `docs/agents/execplans/20260308_loop_python_library_decoupling_packaging_v0.md`
- `docs/agents/execplans/20260308_loop_skills_decoupling_and_project_skills_governance_v0.md`

New files expected during implementation:
- `tests/contract/check_loop_library_ownership_boundary.py`
- `tests/contract/check_loop_repo_split_matrix.py`
- `tests/contract/check_loop_external_consumer_smoke.py`
- `tests/contract/check_loop_skills_repo_contract.py`
- `tests/contract/check_loop_cross_repo_version_matrix.py`
- `docs/setup/LOOP_REPO_SPLIT_QUICKSTART.md`
- version-compatibility manifest(s) to be frozen during phase 1

Registry/index surfaces that must be updated whenever the split adds tests or docs:
- `tests/manifest.json`
- `docs/testing/TEST_MATRIX.md`
- `docs/navigation/FILE_INDEX.md`

Temporary multi-repo workspace convention for local implementation/verification:
- `.cache/leanatlas/tmp/loop_repo_split/looplib_repo/**`
- `.cache/leanatlas/tmp/loop_repo_split/loop_skills_repo/**`
- `.cache/leanatlas/tmp/loop_repo_split/integration_smoke/**`

## Maintainer LOOP execution rule
This split is non-trivial maintainer work on `tools/**`, contracts, tests, and cross-directory ownership. Each implementation phase must therefore close through the required maintainer LOOP path rather than a summary-only manual closeout.

Required sequence for each phase:
- freeze the phase scope under an explicit phase-local child delta ExecPlan derived from this parent; reusing the parent ExecPlan's stable alias across multiple phase closeouts is forbidden
- materialize maintainer graph/session artifacts before edits
- record a `test node` before any `implement node`
- run `verify node`
- run `AI review node`
- publish a phase-local stable maintainer closeout at `artifacts/loop_runtime/by_execplan/<phase_stable_execplan_id>/MaintainerCloseoutRef.json`

Phase handoff rule:
- phase 1, phase 2, and phase 3 must each use distinct stable execplan ids so their closeout aliases remain independently replayable after the full split finishes
- phase 2 must not begin until phase 1 has its own stable maintainer closeout alias
- phase 3 must not begin until phase 2 has its own stable maintainer closeout alias
- if reviewed scope changes after the AI review node, the phase must reopen rather than silently reusing stale closeout evidence

## Milestones
### Phase 1) Invert ownership inside LeanAtlas before extraction
Deliverables:
- `looplib/**` stops being a thin facade over `tools/loop/**` and becomes the internal owner of reusable LOOP implementation
- `tools/loop/**` is reduced to:
  - LeanAtlas-only adapters
  - compatibility shims that delegate to library-owned code
- generic-vs-host boundary is frozen in docs/contracts/tests
- `user_preferences.py` is split so generic policy logic is separable from LeanAtlas-local persistence
- `MaintainerLoopSession` disposition is frozen:
  - move to a neutral `LoopSession`-style surface
  - or keep it LeanAtlas-local with explicit docs/tests

Commands:
- `uv run --locked python tests/contract/check_loop_library_ownership_boundary.py`
- `uv run --locked python tests/contract/check_loop_repo_split_matrix.py`
- `uv run --locked python tests/contract/check_loop_library_packaging.py`
- `uv run --locked python tests/contract/check_loop_contract_docs.py`
- `uv run --locked python tests/contract/check_loop_mainline_docs_integration.py`
- `uv run --locked python tests/contract/check_loop_python_sdk_contract_surface.py`

Acceptance:
- importing `looplib` no longer depends on `tools.loop` being the implementation owner
- no reusable library module imports LeanAtlas workflow-specific code or docs
- LeanAtlas still passes through compatibility shims without changing behavior
- the library/host boundary is enforced by tests rather than prose alone
- phase 1 publishes a stable maintainer closeout alias before phase 2 starts

### Phase 2) Extract the standalone `looplib` repository and cut LeanAtlas over to it
Deliverables:
- create the standalone `looplib` repository with:
  - Python package source
  - contracts/schemas/examples
  - standalone docs
  - its own core verification entrypoints
- move or copy authoritative generic sources from LeanAtlas to the new repo
- switch LeanAtlas from local implementation ownership to pinned consumption of `looplib`
- retain temporary compatibility wrappers in LeanAtlas so old imports fail only under an explicit deprecation policy
- preserve `docs/setup/LOOP_LIBRARY_QUICKSTART.md` in LeanAtlas as a redirect/stub or update all in-repo references in the same phase so LeanAtlas docs/skills never point at a removed local path
- remove the in-repo `looplib/**` package directory from LeanAtlas once the external package cutover happens so repo-root imports cannot shadow the extracted dependency
- add local editable-install and pinned-git-ref smoke paths for development and CI

Commands:
- `export LOOPLIB_REPO=.cache/leanatlas/tmp/loop_repo_split/looplib_repo`
- `uv run --project "$LOOPLIB_REPO" python "$LOOPLIB_REPO/tests/run.py" --profile core`
- `uv run --locked python tests/contract/check_loop_external_consumer_smoke.py --looplib-repo .cache/leanatlas/tmp/loop_repo_split/looplib_repo`
- `uv run --locked python tests/contract/check_loop_cross_repo_version_matrix.py`
- `uv run --locked python tests/contract/check_loop_contract_docs.py`
- `uv run --locked python tests/run.py --profile core`

Acceptance:
- LeanAtlas can run against the external `looplib` checkout instead of repo-local ownership
- standalone docs/examples execute from the external repo without LeanAtlas workflow files
- the dependency graph is one-way: `LeanAtlas -> looplib`, not the reverse
- contracts/schemas used by LeanAtlas for generic LOOP behavior now trace back to the external library owner
- LeanAtlas docs and skills still have a valid local quickstart/redirect path at the end of phase 2
- the LeanAtlas tree no longer contains a shadowing `looplib/**` package directory during the external-consumer smoke
- phase 2 publishes a stable maintainer closeout alias before phase 3 starts

### Phase 3) Extract the standalone generic skills repository and cut LeanAtlas wrappers over to it
Deliverables:
- create the standalone `loop-skills` repository with:
  - generic `loop-*` skills only
  - install/use docs
  - a compatibility manifest keyed to `looplib` versions
- remove generic-skill ownership from LeanAtlas and keep only LeanAtlas-specific wrappers
- remove in-repo generic `.agents/skills/loop-*` entries from LeanAtlas after the cutover so local skill discovery cannot shadow the extracted skills repository
- make LeanAtlas wrappers point to:
  - the external generic skills repo/docs
  - local LeanAtlas workflow docs only for host-specific behavior
- add cross-repo smoke proving a fresh user can consume:
  - external `looplib`
  - external generic skills
  - LeanAtlas wrappers as first-party host adapters

Commands:
- `uv run --locked python tests/contract/check_loop_skills_repo_contract.py --skills-repo .cache/leanatlas/tmp/loop_repo_split/loop_skills_repo`
- `uv run --locked python tests/contract/check_loop_cross_repo_version_matrix.py`
- `uv run --locked python tests/contract/check_skills_standard_headers.py`
- `uv run --locked python tests/contract/check_agents_navigation_coverage.py`
- `uv run --locked python tests/contract/check_loop_external_consumer_smoke.py --looplib-repo .cache/leanatlas/tmp/loop_repo_split/looplib_repo --skills-repo .cache/leanatlas/tmp/loop_repo_split/loop_skills_repo`

Acceptance:
- a non-LeanAtlas user can install/use generic LOOP skills without cloning LeanAtlas
- LeanAtlas keeps only `leanatlas-*` wrappers and host docs
- generic skills and library versions are pinned through an explicit compatibility matrix
- LeanAtlas integration tests prove the three-way composition still works
- the LeanAtlas tree no longer contains shadowing generic `.agents/skills/loop-*` entries during the cross-repo smoke
- phase 3 publishes a stable maintainer closeout alias for the full split state

### Integrated closeout
Deliverables:
- complete cross-repo cutover notes
- deprecation/compatibility window for old LeanAtlas-local import/skill paths
- final authoritative matrix recording:
  - what moved
  - what stayed
  - what compatibility shims remain
- phase-local maintainer LOOP evidence refs and stable closeout aliases for phases 1-3

Commands:
- `uv run --locked python tests/run.py --profile core`
- `uv run --locked python tests/run.py --profile nightly`
- `lake build`
- `git status --porcelain`
- `git diff --check`

Acceptance:
- the split is complete without reopening the already-closed master-plan capability batch
- the remaining LeanAtlas surfaces are clearly host-specific
- future LOOP work can happen in the standalone repos without redefining LeanAtlas as the owner
- `git status --porcelain` is empty after cleaning temporary multi-repo smoke outputs

## Testing plan (TDD)
Add tests before implementation for:
- ownership inversion:
  - `tests/contract/check_loop_library_ownership_boundary.py`
    - fails while `looplib` is still only re-exporting `tools.loop`
    - asserts library-owned modules do not import LeanAtlas workflow-only code
- split matrix correctness:
  - `tests/contract/check_loop_repo_split_matrix.py`
    - enforces the frozen move/stay classification for key files
- external consumer smoke:
  - `tests/contract/check_loop_external_consumer_smoke.py`
    - materializes temporary local checkouts/installs under `.cache/leanatlas/tmp/loop_repo_split/**`
    - proves a non-LeanAtlas consumer path exists
- skills repo contract:
  - `tests/contract/check_loop_skills_repo_contract.py`
    - asserts generic skills carry no LeanAtlas-only routing
    - asserts LeanAtlas wrappers are not treated as generic standalone skills
- cross-repo version matrix:
  - `tests/contract/check_loop_cross_repo_version_matrix.py`
    - proves `LeanAtlas`, `looplib`, and `loop-skills` pin compatible versions intentionally

Regression checks that must continue to pass during the split:
- `tests/contract/check_loop_library_packaging.py`
- `tests/contract/check_loop_contract_docs.py`
- `tests/contract/check_loop_mainline_docs_integration.py`
- `tests/contract/check_loop_python_sdk_contract_surface.py`
- `tests/contract/check_skills_standard_headers.py`
- `tests/contract/check_agents_navigation_coverage.py`
- `tests/run.py --profile core`
- `tests/run.py --profile nightly`

Contamination control:
- all multi-repo integration work must materialize under `.cache/leanatlas/tmp/loop_repo_split/**`
- no test may write sibling repo checkouts into tracked paths
- external-repo smoke must be deterministic with fixed local refs and pinned dependency inputs
- integrated closeout must remove temporary smoke outputs or otherwise restore `git status --porcelain` to empty before the phase closes

## Decision log
- 2026-03-09: do not split repositories before owner inversion; otherwise LeanAtlas remains the hidden implementation owner and the new repos become mirrors rather than authorities.
- 2026-03-09: keep the dependency graph one-way:
  - `looplib` must not depend on LeanAtlas
  - `loop-skills` must not depend on LeanAtlas docs
  - LeanAtlas may depend on both as a first-party host
- 2026-03-09: do not move `worktree_adapter.py` into the standalone library; it is a host strategy, not generic LOOP core.
- 2026-03-09: skills split must happen after library split; otherwise the generic skills repo would have to target an unstable library boundary.
- 2026-03-09: preserve a bounded compatibility-shim window inside LeanAtlas rather than forcing an immediate breaking import rename across all local callers.
- 2026-03-09: freeze version compatibility explicitly; floating default-branch consumption is forbidden for both the library and the skills repositories.
- 2026-03-09: require a distinct child delta ExecPlan per phase so stable closeout aliases are not overwritten by later phases.

## Rollback plan
If the future split proves unstable:
- rollback phase 3 first:
  - re-point LeanAtlas wrappers and docs back to in-repo generic skills
  - disable external skills consumption while preserving the compatibility matrix evidence
- rollback phase 2 next:
  - switch LeanAtlas back from external `looplib` consumption to in-repo ownership shims
  - keep the extracted repo as an experiment branch rather than the authoritative source
- rollback phase 1 last:
  - only if necessary, restore `tools/loop/**` as the internal owner of reusable logic

Rollback verification:
- `uv run --locked python tests/contract/check_loop_mainline_docs_integration.py`
- `uv run --locked python tests/contract/check_loop_python_sdk_contract_surface.py`
- `uv run --locked python tests/run.py --profile core`

## Outcomes & retrospective (fill when done)
- Completed:
- Verification:
- Residual risks:
- Follow-on recommendation:
