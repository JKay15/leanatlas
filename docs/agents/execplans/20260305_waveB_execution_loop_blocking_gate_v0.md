---
title: Wave B M6 - Execute RUNNING<->AI_REVIEW loop and enforce blocking wave gate
owner: Codex (local workspace)
status: done
created: 2026-03-05
---

## Purpose / Big Picture
Wave A/B currently defines contracts, schemas, and low-level runtime pieces, but `tools/loop/sdk.py::run()` still behaves like a scaffold and does not execute a real review-repair loop. This milestone makes Wave execution operational: one call can iterate through `RUNNING -> AI_REVIEW -> ...` until terminal state (`PASSED|FAILED|TRIAGED`) under deterministic stop rules. In parallel, we add a single blocking gate entry that validates a produced Wave execution report against schema and policy invariants (trace contiguity, review-history consistency propagation, budget/terminal coherence). After this work, LOOP execution evidence is both produced and rejected deterministically when invalid, so CI can gate merges on a concrete auditable artifact.

## Glossary
- Wave execution report: one JSON object matching `WaveExecutionLoopRun.schema.json`.
- Blocking gate: deterministic validator that returns non-zero on any schema/policy violation.
- Reviewer adapter: provider-neutral callable returning one review record per round.
- Scripted reviewer: deterministic local reviewer used in tests (no network/LLM dependency).

## Scope
In scope:
- `tools/loop/**` execution/gate runtime extension.
- `tests/contract/**` for TDD and regression checks.
- `docs/contracts/**` and `docs/agents/execplans/**` updates for policy alignment.
- `tests/manifest.json` registration for new deterministic checks.

Out of scope:
- Full MCP server transport implementation.
- Replacing existing Phase2 workflow orchestration.
- Changing Lean formalization experiments under `.cache/leanatlas/tmp/**`.

## Interfaces and Files
Implementation files:
- `tools/loop/sdk.py` (execute loop rounds, emit wave report + refs).
- `tools/loop/runtime.py` (if needed for per-round metadata hooks).
- `tools/loop/wave_gate.py` (new blocking gate validator utilities).
- `tools/loop/__init__.py` (exports).

Test files (TDD first):
- `tests/contract/check_loop_wave_execution_runtime.py` (new: run() executes to terminal and emits valid wave report).
- `tests/contract/check_loop_wave_blocking_gate.py` (new: schema + policy invariants block bad reports).
- targeted updates to existing LOOP contract checks if interfaces change.

Contract/docs:
- `docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md` (explicit blocking gate semantics).
- this ExecPlan file outcome section.

Registry:
- `tests/manifest.json`.

## Milestones
### 1) TDD for real wave execution runtime
Deliverables:
- Add failing test `check_loop_wave_execution_runtime.py` asserting:
  - `sdk.run(..., review_plan=...)` iterates until terminal state.
  - a materialized wave report exists and validates against schema.
  - `REPAIRABLE` loops, budget exits, and `PASS` exit are deterministic.

Commands:
- `uv run --locked python tests/contract/check_loop_wave_execution_runtime.py`

Acceptance:
- Test fails before implementation and passes after implementation.

### 2) TDD for blocking gate
Deliverables:
- Add failing test `check_loop_wave_blocking_gate.py` asserting:
  - valid report passes.
  - non-contiguous transitions fail.
  - contradiction refs not propagated into later `history_context_refs` fail.
  - terminal mismatch (`execution.current_state` vs `final_decision.state`) fails.

Commands:
- `uv run --locked python tests/contract/check_loop_wave_blocking_gate.py`

Acceptance:
- Gate returns deterministic, actionable failure messages and non-zero exit.

### 3) Implement runtime loop + gate
Deliverables:
- Implement `tools/loop/wave_gate.py`.
- Extend `sdk.run()` with optional deterministic review loop input:
  - `review_plan` (list of per-round reviewer outputs) for local execution/testing.
  - provider routing evidence preserved (`agent_provider`, `resolved_invocation_signature`, instruction scope refs).
  - emit `wave_execution/WaveExecutionLoopRun.json` and include its ref in `response.trace_refs`.
- Add strict completion gate check before returning `PASSED` claim under `STRICT`.

Commands:
- `uv run --locked python tests/contract/check_loop_wave_execution_runtime.py`
- `uv run --locked python tests/contract/check_loop_wave_blocking_gate.py`
- `uv run --locked python tests/contract/check_loop_python_sdk_contract_surface.py`
- `uv run --locked python tests/contract/check_loop_wave_execution_policy.py`

Acceptance:
- All above pass and no regression in existing loop contract checks.

### 4) Register gate and close verification
Deliverables:
- Add new tests to `tests/manifest.json`.
- Update contract wording if needed.
- Fill outcomes section in this ExecPlan.

Commands:
- `uv run --locked python tests/run.py --profile core`
- `uv run --locked python tests/run.py --profile nightly`

Acceptance:
- core/nightly pass.

## Testing plan (TDD)
- New deterministic tests:
  - end-to-end wave loop execution from scripted review rounds.
  - blocking gate enforcement and failure diagnostics.
- Regression surface:
  - `check_loop_python_sdk_contract_surface.py`
  - `check_loop_wave_execution_policy.py`
  - `check_loop_review_history_runtime.py`
- Contamination control:
  - all runtime artifacts under temp dirs / `.cache/leanatlas/**`.
  - no writes into Toolbox/Incubator production trees.

## Decision log
- Use `review_plan` deterministic input now to unlock runtime+gate correctness before binding external provider process execution.
- Keep blocking gate as a reusable Python utility + CLI-style contract check for CI.
- Enforce strict completion gate at runtime output boundary, not only isolated helper tests.

## Rollback plan
- Revert files introduced/modified in this plan (`tools/loop/wave_gate.py`, sdk/runtime test additions, manifest updates).
- Re-run:
  - `uv run --locked python tests/contract/check_loop_python_sdk_contract_surface.py`
  - `uv run --locked python tests/contract/check_loop_wave_execution_policy.py`
  - `uv run --locked python tests/run.py --profile core`

## Outcomes & retrospective (fill when done)
- Completed:
- Added deterministic blocking gate implementation:
  - `tools/loop/wave_gate.py`
  - validates schema + trace consistency + budget consistency + review-history consistency/propagation.
- Extended SDK runtime execution:
  - `tools/loop/sdk.py::run(..., review_plan=...)` now executes real `RUNNING <-> AI_REVIEW` loop to terminal.
  - emits `wave_execution/WaveExecutionLoopRun.json` and includes it in `response.trace_refs`.
  - applies strict completion gate (`STRICT + PASSED`) and blocks invalid completion claims.
- Added contract tests:
  - `tests/contract/check_loop_wave_execution_runtime.py`
  - `tests/contract/check_loop_wave_blocking_gate.py`
- Registered tests:
  - `tests/manifest.json` new ids `loop_wave_execution_runtime`, `loop_wave_blocking_gate`
- Updated contracts:
  - `docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md` (blocking gate hard rule)
  - `docs/contracts/LOOP_PYTHON_SDK_CONTRACT.md` (`review_plan` semantics)
- Updated generated testing docs required by gates:
  - `docs/testing/TEST_MATRIX.md`
  - `docs/setup/TEST_ENV_INVENTORY.md`
- Incorporated independent `codex exec` review findings and fixes:
  - evidence: `artifacts/reviews/20260305_waveB_execution_blocking_gate_codex_exec_review.md`
  - Fix A (idempotency replay): strict evidence refs now recover from existing review records on terminal replay (`tools/loop/sdk.py`).
  - Fix B (history semantics): gate no longer forces contradiction refs to be current-iteration finding IDs; it requires propagation through `history_context_refs` (`tools/loop/wave_gate.py`).
  - Added regression tests for both:
    - terminal replay idempotency in `check_loop_wave_execution_runtime.py`
    - external history-ref propagation acceptance in `check_loop_wave_blocking_gate.py`
- Verification:
- TDD failure-before-implementation observed:
  - `run() got an unexpected keyword argument 'review_plan'`
  - `ModuleNotFoundError: tools.loop.wave_gate`
- Post-implementation pass:
  - `uv run --locked python tests/contract/check_loop_wave_execution_runtime.py`
  - `uv run --locked python tests/contract/check_loop_wave_blocking_gate.py`
  - `uv run --locked python tests/contract/check_loop_python_sdk_contract_surface.py`
  - `uv run --locked python tests/contract/check_loop_wave_execution_policy.py`
  - `uv run --locked python tests/contract/check_loop_review_history_runtime.py`
  - `uv run --locked python tests/contract/check_loop_contract_docs.py`
  - `uv run --locked python tests/contract/check_loop_schema_validity.py`
  - `uv run --locked python tests/determinism/check_canonical_json.py`
  - `uv run --locked python tests/run.py --profile core` (pass after regenerating env inventory)
  - `uv run --locked python tests/run.py --profile nightly`
  - `lake build`
- Remaining risks:
- `review_plan` is deterministic local scripted review input; external provider execution (`codex exec`/`claude exec`) is not yet directly invoked by this runtime path.
- blocking gate currently validates one report object at a time; CI wiring for batch artifact sweep can be added as a follow-up.
- Follow-up hardening (2026-03-05):
  - Added explicit post-fix closure hard rules (repair loop must be followed by later review, no prompt/response reuse) and deterministic enforcement:
    - plan: `docs/agents/execplans/20260305_wave_review_closure_hardening_v0.md`
    - gate: `tools/loop/wave_gate.py`
    - tests: `check_loop_wave_blocking_gate.py`, `check_loop_wave_execution_policy.py`, `check_loop_contract_docs.py`
  - Independent `codex exec` review step for this follow-up hit repeated non-terminating CLI behavior; recorded as tooling-triaged evidence:
    - `artifacts/reviews/20260305_wave_review_closure_hardening_codex_exec_review_attempts.md`
    - `artifacts/reviews/20260305_wave_review_closure_hardening_codex_exec_review.md`
