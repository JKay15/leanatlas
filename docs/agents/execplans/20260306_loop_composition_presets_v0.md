---
title: Add LOOP composition presets for task bootstrap and LeanAtlas formalization
owner: Codex
status: done
created: 2026-03-06
---

## Purpose / Big Picture
This plan adds a small preset layer on top of the existing LOOP runtime so the current task can start from a concrete, replayable graph instead of ad-hoc architecture notes. The goal is not to freeze a final global workflow. The goal is to encode two initial compositions as deterministic graph builders: one temporary task-bootstrap loop for repository audit and iterative implementation, and one LeanAtlas paper-formalization loop aligned with the current experimental formalization workflow. These presets must stay easy to revise when experiments expose defects. They should be executable by the current graph runtime, auditable in tests, and narrow enough that later refactors can either promote or replace them without breaking the runtime contracts.

## Glossary
- `composition preset`: a host-local builder that emits a canonical `graph_spec` for a known workflow shape.
- `task bootstrap loop`: the temporary graph for the current engineering task, covering scope freeze, audit, implementation/governor iteration, and closeout.
- `formalization loop`: the LeanAtlas paper workflow graph for evidence gathering, formalization, deterministic gates, mapping alignment, and governor decision.
- `shared resource manifest`: metadata attached to a preset describing which resources are immutable, append-only, or mutable-controlled.

## Scope
In scope:
- add one new LOOP preset/builder module under `tools/loop/`
- add contract-style tests proving the presets are deterministic, graph-valid, and executable by `LoopGraphRuntime`
- expose the preset helpers through `tools.loop`

Out of scope:
- changing LOOP runtime semantics
- changing graph merge rules
- changing review/gate contracts
- moving formalization experiments out of `.cache/leanatlas/tmp/**`
- introducing a generic policy compiler from SOP to graph

Allowed to change:
- `tools/**`
- `tests/**`
- `docs/agents/execplans/**`

Forbidden in this plan:
- `docs/contracts/**` unless the implementation reveals a hard contract mismatch
- experimental `.cache` assets except for reading

## Interfaces and Files
- `docs/agents/execplans/20260306_loop_composition_presets_v0.md`: this plan and decision log.
- `tools/loop/presets.py`: new host-local preset builders and lightweight validation helpers.
- `tools/loop/__init__.py`: export preset helpers.
- `tests/contract/check_loop_composition_presets.py`: TDD coverage for preset topology, resource manifest, and runtime execution.

Expected builder surface:
- `build_task_bootstrap_graph(*, task_id: str) -> dict[str, object]`
- `build_task_bootstrap_bundle(*, task_id: str) -> dict[str, object]`
- `build_formalization_graph(*, paper_id: str) -> dict[str, object]`
- `build_formalization_bundle(*, paper_id: str) -> dict[str, object]`
- `build_dynamic_recovery_graph(*, source_run_key: str, root_cause_signature: str) -> dict[str, object]`
- `build_dynamic_recovery_bundle(*, source_run_key: str, root_cause_signature: str) -> dict[str, object]`
- `build_maintainer_change_graph(*, change_id: str) -> dict[str, object]`
- `build_maintainer_change_bundle(*, change_id: str) -> dict[str, object]`

## Milestones
### Milestone 1: Freeze expected preset shapes in tests
Deliverables:
- `tests/contract/check_loop_composition_presets.py`

Commands:
- `uv run --locked python tests/contract/check_loop_composition_presets.py`

Acceptance:
- test initially fails because preset builders do not exist yet
- test encodes exact node IDs, edge kinds, graph modes, and shared-resource classes

### Milestone 2: Implement preset builders
Deliverables:
- `tools/loop/presets.py`
- `tools/loop/__init__.py`

Commands:
- `uv run --locked python tests/contract/check_loop_composition_presets.py`
- `uv run --locked python tests/contract/check_loop_graph_merge_semantics.py`
- `uv run --locked python tests/contract/check_loop_dynamic_exception_entry_policy.py`

Acceptance:
- preset test passes
- existing graph semantics tests still pass
- dynamic recovery preset is executable and returns to static flow on success

### Milestone 3: Verify repo-level impact
Deliverables:
- updated outcomes and decision log in this plan

Commands:
- `uv run --locked python tests/run.py --profile core`
- `uv run --locked python tests/run.py --profile nightly`
- `lake build`

Acceptance:
- required verification commands pass
- no generated artifacts are committed
- `git status --porcelain` only shows intended source changes before final review

## Testing plan (TDD)
New test coverage:
- temporary task graph contains the expected audit -> nested iteration -> closeout flow
- formalization graph contains evidence, formalization, gate-1, mapping, governor, and final nodes in the intended order
- shared-resource manifests classify immutable, append-only, and mutable-controlled resources explicitly
- dynamic recovery graph is marked `SYSTEM_EXCEPTION_MODE` and succeeds only with unresolved exception context
- all presets are executable by the current `LoopGraphRuntime` using an all-pass executor

Contamination avoidance:
- all runtime executions happen inside `tempfile.TemporaryDirectory`
- no test writes to repository `.cache/leanatlas/**`

## Decision log
- Decision: implement host-local presets, not a new public SDK contract. Rationale: these compositions are intentionally iterative and may change as experiments reveal defects.
- Decision: keep resource manifests inside preset metadata even though the graph runtime does not yet consume them. Rationale: this documents sharing policy now and preserves a promotion path for later arbiter integration.
- Decision: include a dedicated dynamic recovery preset. Rationale: the existing contracts already separate static flow from system exception flow, so the preset layer should expose that split explicitly.
- Decision: register the new contract test in `tests/manifest.json` and regenerate `docs/testing/TEST_MATRIX.md` as part of the same change. Rationale: the repo enforces registry/matrix completeness in `core`, so leaving registration for later would keep the change permanently red.

## Rollback plan
If the preset layer proves unhelpful:
- remove `tools/loop/presets.py`
- drop exports from `tools/loop/__init__.py`
- remove `tests/contract/check_loop_composition_presets.py`
- rerun `uv run --locked python tests/run.py --profile core` and `lake build`

Rollback is safe because no existing runtime semantics are changed.

## Outcomes & retrospective (fill when done)
- Implemented `tools/loop/presets.py` as a schema-valid preset layer with separate bundle sidecars for resource manifests and composition notes.
- Added `task_bootstrap`, `formalization`, `dynamic_recovery`, and `maintainer_change` preset/bundle builders and exported them through `tools/loop/__init__.py`.
- Added contract/runtime coverage in `tests/contract/check_loop_composition_presets.py`, including schema validation, recorded maintainer execution, blocked-node node-results consistency, and collision resistance for dynamic recovery graph IDs.
- Refined the preset layer after reviewer feedback:
  - dynamic recovery graph IDs now incorporate the full `source_run_key`
  - maintainer node results are persisted from actual runtime decisions rather than raw caller input
  - maintainer closeout nodes now opt into terminal-predecessor execution so closeout still runs after triaged/failed AI review
  - maintainer closeout nodes are prevented from improving the upstream AI-review terminal state
  - `GraphSummary.final_status` now preserves the worst admitted terminal class on sink paths, so a passing closeout sink cannot mask an upstream failed AI review
  - `summary_overlay` can no longer overwrite reserved GraphSummary core fields such as `run_key` or `final_status`
  - `allow_terminal_predecessors` is now restricted to sink nodes with at least one `SERIAL | PARALLEL | NESTED | BARRIER` incoming edge
  - recorded maintainer execution now proves write-once artifact compatibility before appending `GraphSummary.jsonl`
  - idempotent replays of the same maintainer run now reuse the existing summary artifact instead of appending a duplicate terminal record
- Verification completed:
  - `uv run --locked python tests/contract/check_loop_composition_presets.py`
  - `uv run --locked python tests/contract/check_loop_graph_merge_semantics.py`
  - `uv run --locked python tests/contract/check_loop_dynamic_exception_entry_policy.py`
  - `uv run --locked python tests/run.py --profile core`
  - `uv run --locked python tests/run.py --profile nightly`
  - `lake build`
- Notes:
  - an early parallel rerun of `core` and `nightly` produced shared-path interference; final verification was rerun sequentially
  - optional real-agent nightly checks skipped as designed because `LEANATLAS_REAL_AGENT_CMD` / `LEANATLAS_REAL_AGENT_PROVIDER` were unset
- Added `tools/loop/presets.py` with deterministic builders for:
  - task bootstrap graph
  - LeanAtlas formalization graph
  - dynamic recovery graph
- Exported the builders through `tools.loop`.
- Added `tests/contract/check_loop_composition_presets.py` to lock node IDs, edge kinds, shared-resource classes, and runtime executability.
- Registered the new test in `tests/manifest.json` and regenerated `docs/testing/TEST_MATRIX.md`.
- Verification performed:
  - `uv run --locked python tests/contract/check_loop_composition_presets.py`
  - `uv run --locked python tests/contract/check_loop_graph_merge_semantics.py`
  - `uv run --locked python tests/contract/check_loop_dynamic_exception_entry_policy.py`
  - `uv run --locked python tests/contract/check_loop_python_sdk_contract_surface.py`
  - `uv run --locked python tests/contract/check_loop_contract_docs.py`
  - `uv run --locked python tests/contract/check_test_registry.py`
  - `uv run --locked python tests/contract/check_test_matrix_up_to_date.py`
  - `uv run --locked python tests/run.py --profile core`
  - `uv run --locked python tests/run.py --profile nightly`
  - `lake build`
- Notes:
  - `core` initially failed on unregistered test detection; fixed by manifest + matrix update.
  - `nightly` optional real-agent checks skipped because `LEANATLAS_REAL_AGENT_CMD` / `LEANATLAS_REAL_AGENT_PROVIDER` were not set, which is accepted by the current tests.
