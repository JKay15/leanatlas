---
title: Require non-trivial maintainer work to materialize and close through LOOP
owner: Codex
status: done
created: 2026-03-06
---

## Purpose / Big Picture
LeanAtlas currently allows a maintainer turn to follow `ExecPlan + TDD + tests + manual closeout` without actually running through a materialized LOOP graph. That leaves a gap between the system we describe and the system we use for system changes. This plan closes that gap by making non-trivial maintainer work LOOP-native: the maintainer path must be represented as a schema-valid graph, tested first, executed with deterministic node evidence, and closed by an AI review node rather than routine manual closeout. The change also fixes the current preset layer so graph builders emit canonical `LoopGraphSpec` objects instead of mixing host metadata into the graph payload. After this plan, LeanAtlas should have a first-class maintainer workflow graph and a deterministic local path to emit graph artifacts for a real maintainer turn.

## Glossary
- `maintainer loop`: the required execution path for a non-trivial maintainer change.
- `graph_spec`: a schema-valid `LoopGraphSpec` object that can be executed by `LoopGraphRuntime`.
- `bundle`: host-local metadata paired with a graph spec, such as shared-resource manifests and descriptive notes.
- `manual closeout`: any closeout path that skips the AI review node; after this plan it is exceptional only.
- `recorded execution`: a graph run where node outcomes are explicitly supplied and persisted into `GraphSummary` / arbitration artifacts.

## Scope
In scope:
- require and document the maintainer-loop sequence `ExecPlan -> graph_spec -> test node -> implement node -> verify node -> AI review node -> LOOP closeout`
- add a schema-valid maintainer graph builder and local execution helper
- refactor existing preset builders so graph payloads remain schema-valid and host metadata moves to sidecar/bundle fields
- add tests for schema validity, maintainer graph order, dynamic recovery graph identity, and recorded graph execution
- run this change through the same maintainer loop pattern locally and emit graph artifacts

Out of scope:
- generic policy-to-graph compilation for every workflow family
- replacing every existing maintainer script with LOOP execution immediately
- changing LOOP graph merge semantics
- changing the AI review provider implementation itself

Allowed to change:
- `tools/**`
- `tests/**`
- `docs/contracts/**`
- `docs/agents/**`

Forbidden in this plan:
- `.cache/leanatlas/tmp/**` except for reading existing experimental material
- root `AGENTS.override.md`

## Interfaces and Files
- `docs/agents/execplans/20260306_maintainer_loop_requirement_v0.md`: this plan and execution record.
- `docs/contracts/LOOP_GRAPH_CONTRACT.md`: clarify schema-valid graph payload vs host metadata sidecar.
- `docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md`: add maintainer-loop closeout requirement and manual-closeout exception boundary.
- `docs/contracts/LOOP_PYTHON_SDK_CONTRACT.md`: document maintainer graph materialization requirement at the SDK surface.
- `docs/agents/PLANS.md`: require non-trivial maintainer work to materialize a maintainer LOOP graph.
- `tools/loop/presets.py`: schema-valid graph builders and host-local bundles, including the maintainer graph.
- `tools/loop/maintainer.py`: deterministic helper to execute recorded maintainer graphs and emit graph artifacts.
- `tools/loop/__init__.py`: export the new maintainer helpers.
- `tests/contract/check_loop_composition_presets.py`: updated preset/bundle/schema tests.
- `tests/contract/check_loop_contract_docs.py`: updated contract-doc snippet checks.
- `tests/contract/check_maintainer_loop_requirement.py`: new contract test for maintainer LOOP requirements.
- `tests/manifest.json`: register the new test(s).
- `docs/testing/TEST_MATRIX.md`: regenerated from the test manifest.

Expected surface:
- `build_maintainer_change_graph(*, change_id: str) -> dict[str, object]`
- `build_maintainer_change_bundle(*, change_id: str) -> dict[str, object]`
- `execute_recorded_graph(*, repo_root: Path, run_key: str, graph_spec: dict[str, object], node_results: dict[str, dict[str, object]], unresolved_exception: bool | None = None) -> dict[str, object]`

## Milestones
### Milestone 1: Freeze requirements in tests
Deliverables:
- `tests/contract/check_loop_composition_presets.py`
- `tests/contract/check_maintainer_loop_requirement.py`
- updates to `tests/contract/check_loop_contract_docs.py`

Commands:
- `uv run --locked python tests/contract/check_loop_composition_presets.py`
- `uv run --locked python tests/contract/check_maintainer_loop_requirement.py`
- `uv run --locked python tests/contract/check_loop_contract_docs.py`

Acceptance:
- tests fail before implementation changes
- tests require schema-valid graph specs, bundle sidecars, maintainer node order, and doc snippets

### Milestone 2: Implement schema-valid presets and maintainer execution helper
Deliverables:
- `tools/loop/presets.py`
- `tools/loop/maintainer.py`
- `tools/loop/__init__.py`

Commands:
- `uv run --locked python tests/contract/check_loop_composition_presets.py`
- `uv run --locked python tests/contract/check_loop_dynamic_exception_entry_policy.py`
- `uv run --locked python tests/contract/check_loop_graph_merge_semantics.py`

Acceptance:
- graph builders emit schema-valid `LoopGraphSpec` payloads
- bundle metadata is available without polluting graph schema
- maintainer recorded execution emits `GraphSummary` through `LoopGraphRuntime`
- dynamic recovery graph identity is stable and collision-resistant

### Milestone 3: Wire docs and registry
Deliverables:
- updated contract docs and planning rules
- `tests/manifest.json`
- regenerated `docs/testing/TEST_MATRIX.md`

Commands:
- `uv run --locked python tests/contract/check_loop_contract_docs.py`
- `uv run --locked python tests/contract/check_test_registry.py`
- `uv run --locked python tests/contract/check_test_matrix_up_to_date.py`

Acceptance:
- maintainer LOOP requirement is documented in committed policy docs
- new tests are fully registered and matrix is up to date

### Milestone 4: Verify and execute this turn through the maintainer loop
Deliverables:
- updated Outcomes section in this plan
- local graph artifacts for this turn under `artifacts/loop_runtime/by_key/<run_key>/graph/*`
- AI review artifacts under `artifacts/reviews/*`

Commands:
- `uv run --locked python tests/run.py --profile core`
- `uv run --locked python tests/run.py --profile nightly`
- `lake build`
- local recorded maintainer-loop execution command
- `codex exec review ...`

Acceptance:
- required verification passes
- maintainer graph artifacts exist for this turn
- closeout references either real `REVIEW_RUN` artifacts or an explicit tooling-triage record

## Testing plan (TDD)
New or changed coverage:
- preset graphs validate against `LoopGraphSpec.schema.json`
- bundle metadata is separate from the graph payload
- maintainer graph contains the exact required node chain
- dynamic recovery graph identity changes when `source_run_key` changes under the same root cause
- recorded maintainer execution can emit `GraphSummary` with all nodes passing
- contract docs and planning rules require maintainer LOOP materialization

Contamination avoidance:
- tests use `tempfile.TemporaryDirectory`
- no committed test writes into repo `.cache/leanatlas/**`
- local graph/review artifacts stay under ignored `artifacts/**`

## Decision log
- Decision: treat `ExecPlan`, `TDD`, and verification as LOOP nodes rather than external process phases. Rationale: maintainer work should exercise the same execution system it claims to maintain.
- Decision: keep graph payloads schema-valid and move resource manifests/notes into bundle sidecars. Rationale: `LoopGraphSpec.schema.json` has `additionalProperties: false`.
- Decision: implement a recorded-execution helper first, not a full arbitrary command runner. Rationale: this is enough to make maintainer turns auditable immediately without introducing a large execution framework in one patch.

## Rollback plan
If the maintainer-loop requirement causes operational friction:
- remove the new maintainer contract test and helper module
- revert contract doc wording and planning rule changes
- keep preset builders but drop maintainer-specific exports
- rerun `uv run --locked python tests/run.py --profile core` and `lake build`

## Outcomes & retrospective (fill when done)
- Implemented schema-valid preset/bundle separation in `tools/loop/presets.py` and added a first-class `maintainer_change` graph that encodes `ExecPlan -> graph_spec -> test node -> implement node -> verify node -> AI review node -> LOOP closeout`.
- Added `tools/loop/maintainer.py` with `execute_recorded_graph(...)` so a maintainer turn can emit deterministic `GraphSpec.json`, `NodeResults.json`, and `GraphSummary.jsonl` artifacts through `LoopGraphRuntime`.
- Strengthened the helper after review-driven fixes:
  - `NodeResults.json` now reflects actual executed/blocked runtime decisions
  - `jsonschema` loading for maintainer-only validation is deferred until execution time
  - conflicting reruns on the same `run_key` now fail before appending a new `GraphSummary.jsonl` record, so write-once `NodeResults.json` cannot drift from summary history
  - idempotent replays of the same recorded maintainer result now reuse the existing `GraphSummary.jsonl` entry instead of appending duplicate terminal summaries
  - maintainer `loop_closeout` now executes after terminal AI-review outcomes instead of being forced into implicit `UPSTREAM_BLOCKED`
  - maintainer `loop_closeout` is now constrained to preserve the `ai_review_node` terminal state, so closeout cannot incorrectly upgrade a failed/triaged review to `PASSED`
  - `LoopGraphRuntime` now preserves the upstream terminal class in `GraphSummary.final_status`, so a passing closeout sink cannot downgrade a failed/triaged maintainer review
  - `summary_overlay` is now additive-only and rejects attempts to override reserved GraphSummary core fields
  - `allow_terminal_predecessors` is now contract-enforced to require at least one `SERIAL | PARALLEL | NESTED | BARRIER` incoming edge on a sink node
- parent-repo contract enforcement was kept within the parent repo after identifying that `.agents/skills` is a separate submodule boundary
- Documented the maintainer LOOP requirement in:
  - `docs/agents/PLANS.md`
  - `docs/contracts/LOOP_GRAPH_CONTRACT.md`
  - `docs/contracts/LOOP_PYTHON_SDK_CONTRACT.md`
  - `docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md`
- Added/updated coverage in:
  - `tests/contract/check_loop_composition_presets.py`
  - `tests/contract/check_maintainer_loop_requirement.py`
  - `tests/contract/check_loop_contract_docs.py`
  - `tests/manifest.json`
  - `docs/testing/TEST_MATRIX.md`
- Verification completed on the final diff:
  - `uv run --locked python tests/contract/check_loop_composition_presets.py`
  - `uv run --locked python tests/contract/check_maintainer_loop_requirement.py`
  - `uv run --locked python tests/contract/check_loop_contract_docs.py`
  - `uv run --locked python tests/contract/check_skills_standard_headers.py`
  - `uv run --locked python tests/run.py --profile core`
  - `uv run --locked python tests/run.py --profile nightly`
  - `lake build`
- Review iterations exposed two real issues before final closeout:
  - local submodule-only skill edits must not be enforced by parent-repo contract tests without a promoted submodule commit
  - review attempts must be refreshed whenever the diff changes mid-review
- Final review iterations also tightened two runtime behaviors:
  - summary persistence now happens only after maintainer write-once artifacts are proven compatible for that `run_key`
  - lazy package access to `tools.loop.run` no longer pulls `jsonschema` eagerly through `wave_gate`
