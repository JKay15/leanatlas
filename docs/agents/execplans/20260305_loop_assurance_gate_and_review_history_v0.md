---
title: Enforce LOOP assurance-level gate (FAST/LIGHT/STRICT) and operationalize review-history evidence
owner: Codex (local workspace)
status: done
created: 2026-03-05
---

## Purpose / Big Picture
We need a deterministic guardrail that prevents STRICT Wave work from being reported as complete without AI review evidence, while allowing FAST/LIGHT tasks to avoid unnecessary token/time cost. This plan introduces assurance-level semantics (`FAST`, `LIGHT`, `STRICT`) into LOOP contracts/schemas and adds machine-checkable gates in `tests/contract/**`. It also upgrades runtime-side review-history handling so the history is not only passed through but summarized into deterministic consistency evidence. The outcome should be: (1) strict work cannot bypass `codex exec` evidence, (2) non-strict work can remain lightweight, and (3) review-history availability is verifiable by tests and artifacts.

## Glossary
- Assurance level: policy tier controlling required AI-review evidence (`FAST`, `LIGHT`, `STRICT`).
- Strict completion gate: deterministic rule that blocks STRICT Wave completion claims when required review evidence files are missing.
- Review-history consistency summary: deterministic counts/refs of contradiction/nitpick signals derived from review history records.

## Scope
In scope:
- `docs/contracts/LOOP_RUNTIME_CONTRACT.md`
- `docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md`
- `docs/contracts/LOOP_PYTHON_SDK_CONTRACT.md`
- `docs/schemas/WaveExecutionLoopRun.schema.json`
- `tools/loop/**` (runtime/SDK helpers for assurance + review-history summary)
- `tests/contract/**` (new/updated gates)
- `tests/manifest.json`
- `docs/testing/TEST_MATRIX.md`
- this ExecPlan

Out of scope:
- Full LOOP graph scheduling semantics redesign
- third MCP service implementation
- migration of all historical Wave records

Allowed directories:
- `tools/**`, `tests/**`, `docs/contracts/**`, `docs/schemas/**`, `docs/testing/**`, `docs/agents/execplans/**`

Forbidden:
- `LeanAtlas/**`, `Problems/**` (except temporary `.cache` artifacts produced by tests)

## Interfaces and Files
Planned new files:
- `tools/loop/assurance.py` (assurance level model + strict evidence requirement evaluator)
- `tools/loop/review_history.py` (deterministic review-history summary extractor)
- `tests/contract/check_loop_assurance_gate_policy.py`
- `tests/contract/check_loop_review_history_runtime.py`

Planned modified files:
- `tools/loop/sdk.py`
- `tools/loop/__init__.py`
- `docs/contracts/LOOP_RUNTIME_CONTRACT.md`
- `docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md`
- `docs/contracts/LOOP_PYTHON_SDK_CONTRACT.md`
- `docs/schemas/WaveExecutionLoopRun.schema.json`
- `tests/contract/check_loop_contract_docs.py`
- `tests/contract/check_loop_schema_validity.py`
- `tests/contract/check_loop_wave_execution_policy.py`
- `tests/contract/fixtures/loop/positive/waveexecutionlooprun_min.json`
- `tests/contract/fixtures/loop/negative/waveexecutionlooprun_bad_trace_flags.json`
- `tests/contract/fixtures/loop/negative/waveexecutionlooprun_missing_review_evidence.json`
- `tests/manifest.json`
- `docs/testing/TEST_MATRIX.md`
- `docs/agents/execplans/20260305_loop_waveB_runtime_sdk_v0.md` (append-only verification note if needed)

## Milestones
### 1) Contracts + schema assurance-level freeze (TDD-first)
Deliverables:
- Update LOOP contracts to define FAST/LIGHT/STRICT principles and strict completion gate.
- Extend `WaveExecutionLoopRun.schema.json` with `assurance_level` and strict evidence constraints.
- Update/expand schema fixtures for new required fields.

Commands:
- `uv run --locked python tests/contract/check_loop_contract_docs.py`
- `uv run --locked python tests/contract/check_loop_schema_validity.py`

Acceptance:
- Contracts contain explicit assurance-level rules and strict gate wording.
- Schema/fixtures validate deterministically.

### 2) Strict gate checker (process-level deterministic policy)
Deliverables:
- Add `check_loop_assurance_gate_policy.py` validating strict evidence expectations from sample Wave instances and/or policy objects.
- Ensure strict mode requires `codex exec` review evidence refs before PASSED.

Commands:
- `uv run --locked python tests/contract/check_loop_assurance_gate_policy.py`
- `uv run --locked python tests/contract/check_loop_wave_execution_policy.py`

Acceptance:
- Missing strict evidence fails deterministically.
- FAST/LIGHT policy paths remain non-blocking.

### 3) Review-history runtime operationalization
Deliverables:
- Add deterministic review-history summary helper (`tools/loop/review_history.py`).
- Integrate summary generation into SDK run path when `review_history` is provided.
- Add runtime contract test proving summary artifact is generated and stable.

Commands:
- `uv run --locked python tests/contract/check_loop_review_history_runtime.py`
- `uv run --locked python tests/contract/check_loop_sdk_error_envelope_runtime.py`

Acceptance:
- Review history is not only stored but summarized into deterministic consistency evidence.
- Summary output is traceable from SDK response refs.

### 4) Registry + matrix + full verification
Deliverables:
- Register added tests in manifest.
- Regenerate test matrix.
- Run full core/nightly verification.

Commands:
- `uv run --locked python tests/contract/check_test_registry.py`
- `uv run --locked python tests/contract/check_test_matrix_up_to_date.py`
- `uv run --locked python tests/run.py --profile core`
- `uv run --locked python tests/run.py --profile nightly`

Acceptance:
- New tests are discoverable and matrix is up-to-date.
- Core/nightly pass (expected skips allowed by policy).

## Testing plan (TDD)
New tests first:
- `check_loop_assurance_gate_policy.py`:
  - strict mode without AI-review evidence must fail
  - strict mode with prompt/response/summary refs passes
  - fast/light modes do not hard-block completion
- `check_loop_review_history_runtime.py`:
  - SDK run with review_history emits summary artifact
  - contradiction/nitpick counters and refs are deterministic

Updated tests:
- `check_loop_contract_docs.py`
- `check_loop_schema_validity.py`
- `check_loop_wave_execution_policy.py`

Contamination control:
- test artifacts under temporary dirs or `.cache/leanatlas/**`
- no writes to production Toolbox/Incubator

## Decision log
- Assurance-level gate is policy-scoped: strict for auditable completion, lightweight for exploratory flow.
- Strict compliance is enforced by deterministic checks, not human memory.
- Review-history support is upgraded from pass-through storage to explicit summary evidence.

## Rollback plan
- Revert modified LOOP contracts/schema/tests/tools in this plan.
- Re-run:
  - `uv run --locked python tests/run.py --profile core`
  - `uv run --locked python tests/contract/check_test_registry.py`

## Outcomes & retrospective (fill when done)
- Completed:
  - Added assurance policy/runtime helpers:
    - `tools/loop/assurance.py`
    - `tools/loop/review_history.py`
  - Integrated assurance + review-history surfaces into runtime outputs:
    - `tools/loop/sdk.py`
    - `tools/loop/__init__.py`
  - Updated contracts/schemas/fixtures for FAST|LIGHT|STRICT and strict completion evidence:
    - `docs/contracts/LOOP_RUNTIME_CONTRACT.md`
    - `docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md`
    - `docs/contracts/LOOP_PYTHON_SDK_CONTRACT.md`
    - `docs/schemas/WaveExecutionLoopRun.schema.json`
    - `tests/contract/fixtures/loop/positive/waveexecutionlooprun_min.json`
    - `tests/contract/fixtures/loop/negative/waveexecutionlooprun_bad_trace_flags.json`
    - `tests/contract/fixtures/loop/negative/waveexecutionlooprun_missing_review_evidence.json`
  - Added deterministic contract tests:
    - `tests/contract/check_loop_assurance_gate_policy.py`
    - `tests/contract/check_loop_review_history_runtime.py`
  - Added/updated independent `codex exec` audit chain with iterative fixes and closeout refresh:
    - `artifacts/reviews/20260305_loop_assurance_codex_exec_review.md`
    - `artifacts/reviews/20260305_loop_assurance_codex_exec_review_after_fix_v4.md`
    - `artifacts/reviews/20260306_stage2_active_plans_closeout_review_round2_response.md`
- Verification summary:
  - `uv run --locked python tests/contract/check_loop_assurance_gate_policy.py` PASS
  - `uv run --locked python tests/contract/check_loop_review_history_runtime.py` PASS
  - `uv run --locked python tests/contract/check_loop_sdk_error_envelope_runtime.py` PASS
  - `uv run --locked python tests/contract/check_loop_wave_execution_policy.py` PASS
  - `uv run --locked python tests/contract/check_loop_contract_docs.py` PASS
  - `uv run --locked python tests/contract/check_loop_schema_validity.py` PASS
  - `uv run --locked python tests/contract/check_test_registry.py` PASS
  - `uv run --locked python tests/contract/check_test_matrix_up_to_date.py` PASS
  - `uv run --locked python tests/run.py --profile core` PASS
  - `uv run --locked python tests/run.py --profile nightly` PASS
- Residual risks:
  - Reviewer process reliability is still environment-sensitive; stall cases are triaged with reproducible attempt logs.
- Deferred:
  - Deeper semantic contradiction mining remains deterministic-summary based and can be extended in later waves.
