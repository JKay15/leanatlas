---
title: Default non-trivial execution through a root-supervisor-first LOOP path
owner: Codex (local workspace)
status: done
created: 2026-03-09
parent_execplan: docs/agents/execplans/20260307_loop_core_parallel_nested_batch_v0.md
---

## Purpose / Big Picture
The current repository has the runtime pieces for maintainer sessions, batch supervision, review orchestration, publication/rematerialization, and host adapters, but it still leaves too much room for the conversation-facing agent to act like the primary worker. That is the wrong default when non-trivial LOOP capabilities already exist. This plan hardens a root-supervisor-first default path: the conversation agent must first freeze an ExecPlan, materialize a root-level LOOP session/skeleton, and then delegate into child supervisors, child loops, and workers. The hardening must be owned by the reusable LOOP library surface, not by LeanAtlas-only prose, so generic contracts/docs/tests become authoritative and LeanAtlas workflow docs merely map the host-specific wrapper semantics. The bounded goal is to enforce root-supervisor evidence, explicit manual/direct exception artifacts, and auditable delegation/session/closeout lineage without rewriting the existing runtime.

## Glossary
- root supervisor kernel: the conversation-facing task agent that freezes scope, materializes the top-level LOOP session/skeleton, delegates work, issues exceptions, and owns the integrated closeout decision.
- wave supervisor: a parent supervisor that coordinates multiple child waves through `materialize_batch_supervisor(...)` / `execute_batch_supervisor(...)`.
- subgraph supervisor: a narrower supervisor for a local staged review bundle, maintainer change graph, or exception-recovery graph.
- worker / node executor: the concrete execution lane for a node or child wave. This may be a callable, a host adapter, or a review stage, but it is not the final authority for task closeout.
- root-level LOOP skeleton artifact: an auditable artifact under the current run that declares the root-supervisor nodes, delegated child types, exception/fallback path, and integrated closeout path before implementation begins.
- root-issued exception artifact: an auditable artifact emitted by the root supervisor when direct/manual fallback is allowed for a blocked subtree.
- non-trivial task: any task satisfying one or more of the criteria below and therefore requiring LOOP-first execution.

## Scope
In scope:
- reusable LOOP contracts/docs/tests for root-supervisor-first non-trivial execution
- generic `looplib` / `tools/loop` helper surfaces for root skeleton and root-issued exception artifacts
- closeout enforcement that requires root delegation/session evidence before a non-trivial maintainer session can close
- generic skills/docs for `loop-mainline` / `loop-batch-supervisor` / `LOOP_LIBRARY_QUICKSTART`
- LeanAtlas wrapper docs/skills only where they must map `conversation Codex = root supervisor kernel`

Out of scope:
- rewriting the whole maintainer runtime or batch supervisor runtime
- new autopilot/productization themes beyond this default-execution hardening
- new reviewer-policy experiments
- formalization-frontier work
- external repository split implementation

## Non-trivial classification
Treat a task as non-trivial if any of the following is true:
- it requires changes to two or more repo files
- it changes any system surface under `tools/**`, `docs/contracts/**`, `tests/**`, `docs/agents/**`, or `.agents/skills/**`
- it adds or changes tests, closeout semantics, workflow routing, review behavior, contracts, or skills
- it requires fresh AI review closeout
- it needs any exception/fallback explanation

Only a pure single-point wording fix that does not affect workflow/contract/test/routing/skills/closeout semantics may be treated as trivial.

## Interfaces and Files
Authoritative reusable surfaces:
- `tools/loop/maintainer.py`
- `looplib/session.py`
- `looplib/__init__.py`
- `docs/contracts/LOOP_GRAPH_CONTRACT.md`
- `docs/contracts/LOOP_RUNTIME_CONTRACT.md`
- `docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md`
- `docs/contracts/LOOP_PYTHON_SDK_CONTRACT.md`
- `docs/setup/LOOP_LIBRARY_QUICKSTART.md`
- `.agents/skills/loop-mainline/SKILL.md`
- `.agents/skills/loop-batch-supervisor/SKILL.md`

Wrapper/routing sync surfaces:
- `AGENTS.md`
- `docs/agents/LOOP_MAINLINE.md`
- `docs/agents/MAINTAINER_WORKFLOW.md`
- `docs/agents/OPERATOR_WORKFLOW.md`
- `.agents/skills/leanatlas-loop-mainline/SKILL.md`
- `.agents/skills/leanatlas-loop-maintainer-ops/SKILL.md`

Tests:
- `tests/contract/check_loop_maintainer_session.py`
- `tests/contract/check_loop_contract_docs.py`
- `tests/contract/check_loop_python_sdk_contract_surface.py`
- `tests/contract/check_loop_library_packaging.py`
- `tests/contract/check_loop_mainline_docs_integration.py`
- `tests/contract/check_loop_batch_supervisor.py`
- `tests/manifest.json`
- `docs/testing/TEST_MATRIX.md`

New reusable artifact shapes to introduce or harden:
- `artifacts/loop_runtime/by_key/<run_key>/graph/root_supervisor_skeleton.json`
- `artifacts/loop_runtime/by_key/<run_key>/graph/root_supervisor_exception.json` or a stable rooted variant under the same graph directory

## Milestones
### M1. Freeze scope, materialize root session, and write the root-supervisor skeleton
Deliverables:
- this ExecPlan
- materialized maintainer session for this exact plan
- auditable root-level skeleton artifact bound to the materialized run

Commands:
- `sed -n '1,260p' docs/agents/execplans/20260309_loop_root_supervisor_default_execution_v0.md`
- `python - <<'PY' ... materialize_maintainer_session(...) ... PY`

Acceptance:
- no implementation files are edited before the ExecPlan exists
- a run-keyed maintainer session exists before implementation
- a run-keyed root-supervisor skeleton artifact exists before implementation

### M2. Add TDD coverage for root-supervisor-first closeout and exception artifacts
Deliverables:
- expanded maintainer/runtime/doc tests covering:
  - non-trivial closeout requires root skeleton/delegation evidence
  - manual/direct fallback requires a root-issued exception artifact
  - fallback is bounded to the blocked subtree only
  - docs/skills describe root supervisor + layered supervisors clearly

Commands:
- `uv run --locked python tests/contract/check_loop_maintainer_session.py`
- `uv run --locked python tests/contract/check_loop_contract_docs.py`
- `uv run --locked python tests/contract/check_loop_python_sdk_contract_surface.py`
- `uv run --locked python tests/contract/check_loop_library_packaging.py`
- `uv run --locked python tests/contract/check_loop_mainline_docs_integration.py`

Acceptance:
- tests fail before implementation because root skeleton / exception gating / delegation evidence are not yet enforced

### M3. Implement generic root-supervisor runtime/wiring and sync wrapper docs
Deliverables:
- reusable helper surfaces for root skeleton and root-issued exception artifacts
- non-trivial maintainer closeout enforcement for required root delegation/session evidence
- authoritative generic contract/doc/skill updates
- LeanAtlas wrapper docs/skills synced without becoming the authority

Commands:
- `uv run --locked python tests/contract/check_loop_maintainer_session.py`
- `uv run --locked python tests/contract/check_loop_contract_docs.py`
- `uv run --locked python tests/contract/check_loop_python_sdk_contract_surface.py`
- `uv run --locked python tests/contract/check_loop_library_packaging.py`
- `uv run --locked python tests/contract/check_loop_mainline_docs_integration.py`

Acceptance:
- non-trivial maintainer closeout fails closed without root skeleton/delegation evidence
- manual/direct fallback requires a root-issued exception artifact with the required fields
- generic docs/skills explain the layered supervisor model and root authority

### M4. Verify and close under the committed reviewer policy
Deliverables:
- passing verification on the final byte state
- fresh AI review closeout covering the plan, root skeleton, any exception artifact, and final evidence chain

Commands:
- `uv run --locked python tests/run.py --profile core`
- `uv run --locked python tests/run.py --profile nightly`
- `lake build`
- `git diff --check`

Acceptance:
- verification passes on the final byte state
- closeout uses the committed default reviewer path (`FAST + low`, bounded `medium`) and not `xhigh`

## Testing plan (TDD)
- Extend `tests/contract/check_loop_maintainer_session.py` so non-trivial maintainer closeout requires:
  - a materialized root-supervisor skeleton artifact
  - delegation evidence mapping root-supervisor nodes to child execution refs
  - bounded manual/direct exceptions to be backed by a root-issued exception artifact
- Extend `tests/contract/check_loop_contract_docs.py` and `tests/contract/check_loop_python_sdk_contract_surface.py` so contracts require:
  - root supervisor kernel semantics
  - layered supervisor semantics
  - explicit exception artifact shape
  - delegation/session/closeout evidence mapping
- Extend `tests/contract/check_loop_library_packaging.py` and `tests/contract/check_loop_mainline_docs_integration.py` so generic docs/skills are authoritative and LeanAtlas wrappers route into them cleanly.
- Update manifest/test-matrix surfaces if a new contract test file or new required test command is introduced.

## Decision log
- Make generic LOOP contracts/docs/skills authoritative; LeanAtlas workflow docs remain wrapper routing only.
- Reuse the existing maintainer session and batch-supervisor surfaces instead of introducing a new root runtime.
- Enforce root-supervisor evidence through stable artifacts, not through conversational promises.
- Keep manual/direct fallback as a bounded exception for blocked subtrees only; never let local blockage waive the whole task out of LOOP mode.

## Rollback plan
- Revert changes in:
  - `tools/loop/maintainer.py`
  - `looplib/session.py`
  - `looplib/__init__.py`
  - generic contracts/docs/skills
  - synced LeanAtlas wrapper docs/skills
  - affected tests/manifest/matrix
- Re-run:
  - `uv run --locked python tests/contract/check_loop_maintainer_session.py`
  - `uv run --locked python tests/contract/check_loop_contract_docs.py`
  - `uv run --locked python tests/contract/check_loop_python_sdk_contract_surface.py`
  - `uv run --locked python tests/run.py --profile core`
  - `lake build`

## Outcomes & retrospective (fill when done)
- Generic LOOP library surfaces are now authoritative for this behavior:
  - `tools/loop/maintainer.py`
  - `docs/contracts/LOOP_GRAPH_CONTRACT.md`
  - `docs/contracts/LOOP_PYTHON_SDK_CONTRACT.md`
  - `docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md`
  - `docs/setup/LOOP_LIBRARY_QUICKSTART.md`
  - `tests/contract/check_loop_maintainer_session.py`
- LeanAtlas wrapper docs/skills remain routing-only wrappers around the generic semantics; this wave did not move authority back into LeanAtlas-only prose.
- Root-supervisor-first enforcement now covers:
  - required root skeleton/delegation artifacts before implementation
  - session-bound root-issued exception artifacts for direct/manual fallback
  - closeout rejection for stale or hand-edited root skeleton contents
  - closeout rejection when a multi-entry root exception artifact contains globally overlapping `affected_node_ids`, even if the overlap is outside the currently journaled direct/manual node
- Verification on the final byte state passed:
  - `uv run --locked python tests/run.py --profile core`
  - `uv run --locked python tests/run.py --profile nightly`
  - `lake build`
  - `git diff --check`
  - verify note: `artifacts/verify/20260309_loop_root_supervisor_default_execution_verify.md`
- Review history for this wave:
  - low rounds 1-2 and medium rounds 3-7 established the earlier enforcement gaps and two tooling stalls
  - interactive round 8 surfaced the final remaining global-overlap validation bug, now fixed
  - post-fix interactive rounds 9-10 did not yield a terminal response artifact despite repeated supervisor guidance; tooling evidence is preserved in `artifacts/reviews/20260309_loop_root_supervisor_default_execution_interactive_review_attempts.md`
- Authoritative maintainer closeout for the rematerialized final session is:
  - run key `5b081dff8baa2263357550000397276004946dc6ff7b26315a5a46560d0c964a`
  - stable closeout ref `artifacts/loop_runtime/by_execplan/docs__agents__execplans__20260309_loop_root_supervisor_default_execution_v0.md__47c1775a395d/MaintainerCloseoutRef.json`
  - final runtime status `TRIAGED` because fresh post-fix reviewer tooling never produced a usable terminal response artifact
