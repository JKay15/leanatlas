---
title: Enforce Wave-A execution itself as a strict meta-loop with AI review and deterministic exit
owner: Codex (local workspace)
status: done
created: 2026-03-05
---

## Purpose / Big Picture
Wave A currently freezes LOOP contracts/schemas/policy gates, but the Wave-A implementation process itself is not yet contractized as a strict execution loop. We need a deterministic meta-loop contract so each Wave execution follows: implementation -> AI review -> repair loop/terminal decision, with explicit stop rules and evidence. This removes ambiguity, prevents ad-hoc review behavior, and aligns with the requirement that AI review can be executed via `codex exec review` (or equivalent) with reproducible artifacts. The goal of this plan is to make this governance machine-checkable using contracts, schema, and tests.

## Glossary
- Wave execution meta-loop: the process-level loop for implementing a Wave.
- AI review verdict: deterministic review classification used by transition logic.
- Strict exit mechanism: bounded retries + stagnation + non-retryable/blocker rules.
- Repair loop: `AI_REVIEW -> RUNNING` transition when issue is repairable and budget remains.

## Scope
In scope:
- `docs/contracts/**` (new Wave-execution contract)
- `docs/schemas/**` (new Wave-execution run schema)
- `tests/contract/**` (new/updated deterministic checks)
- `tests/contract/fixtures/loop/**` (positive/negative fixtures)
- `tests/manifest.json`
- `docs/testing/TEST_MATRIX.md` (regenerated)
- `docs/agents/execplans/**` (this plan updates)

Out of scope:
- Runtime engine implementation under `tools/loop/**`
- MCP server implementation
- Existing theorem formalization artifacts under `.cache/leanatlas/tmp/**`

## Interfaces and Files
Planned files:
- `docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md` (new)
- `docs/schemas/WaveExecutionLoopRun.schema.json` (new)
- `tests/contract/check_loop_wave_execution_policy.py` (new)
- `tests/contract/check_loop_contract_docs.py` (update required docs/snippets)
- `tests/contract/check_loop_schema_validity.py` (register new schema + semantic checks)
- `tests/contract/fixtures/loop/positive/waveexecutionlooprun_min.json` (new)
- `tests/contract/fixtures/loop/negative/waveexecutionlooprun_missing_review_evidence.json` (new)
- `tests/manifest.json` (register new test)
- `docs/testing/TEST_MATRIX.md` (regen)

## Milestones
### 1) TDD red gates for meta-loop semantics
Deliverables:
- Add/extend tests so current tree fails without new contract/schema.

Commands:
- `uv run --locked python tests/contract/check_loop_contract_docs.py`
- `uv run --locked python tests/contract/check_loop_schema_validity.py`
- `uv run --locked python tests/contract/check_loop_wave_execution_policy.py`

Acceptance:
- At least one of the above fails before contract/schema implementation.

### 2) Contract + schema + fixtures implementation
Deliverables:
- Add Wave-execution contract with strict AI-review fields and deterministic transition rules.
- Add schema and positive/negative fixtures.

Commands:
- `uv run --locked python tests/contract/check_loop_schema_validity.py`
- `uv run --locked python tests/contract/check_loop_wave_execution_policy.py`

Acceptance:
- Tests pass and enforce:
  - review verdict taxonomy,
  - repair-loop condition,
  - bounded retry exit,
  - stagnation triage,
  - non-retryable/blocker terminal transitions.

### 3) Registry/docs synchronization
Deliverables:
- Register new contract test in manifest.
- Regenerate deterministic matrix.

Commands:
- `uv run --locked python tests/contract/check_test_registry.py`
- `uv run --locked python tools/tests/generate_test_matrix.py --write`
- `uv run --locked python tests/contract/check_test_matrix_up_to_date.py`

Acceptance:
- Registry and matrix checks pass.

### 4) Full verification
Deliverables:
- Core + nightly verification for touched contracts/tests.

Commands:
- `uv run --locked python tests/run.py --profile core`
- `uv run --locked python tests/run.py --profile nightly`

Acceptance:
- Both profiles pass.

### 5) AI-review evidence run (codex exec)
Deliverables:
- Run one `codex exec` review for Wave-A loop contracts/policy and save evidence under temporary artifacts.

Commands:
- `codex exec --ephemeral -C /Users/xiongjiangkai/xjk_papers/leanatlas -o /tmp/waveA_meta_loop_ai_review.txt "<review prompt>"`

Acceptance:
- Review output includes explicit verdict + actionable findings or clean pass; result is summarized in this plan.

## Testing plan (TDD)
New/updated tests:
- Add `check_loop_wave_execution_policy.py` for deterministic transition/stop-rule behavior.
- Extend doc/schema checks to require Wave execution meta-loop contract and schema coverage.

Regression scenarios covered:
- Missing strict AI-review verdict fields.
- Missing retry/stagnation stop mechanism.
- Illegal transitions (e.g., direct RUNNING->PASSED).
- Missing review evidence references.

Contamination control:
- No writes to Toolbox/Incubator.
- No runtime implementation changes.
- Temporary AI-review outputs only under `/tmp`.

## Decision log
- Keep Wave execution governance in a separate contract to avoid overloading runtime node contract.
- Enforce deterministic policy via contract tests (no LLM-dependent pass criteria).
- Keep human review non-blocking and post-hoc (evidence/audit), not execution-path gating.

## Rollback plan
- Revert only files listed in Interfaces and Files.
- Re-run:
  - `uv run --locked python tests/contract/check_loop_contract_docs.py`
  - `uv run --locked python tests/contract/check_loop_schema_validity.py`
  - `uv run --locked python tests/run.py --profile core`

## Outcomes & retrospective (fill when done)
- Completed:
  - Added Wave-A execution meta-loop contract + schema + fixtures:
    - `docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md`
    - `docs/schemas/WaveExecutionLoopRun.schema.json`
    - `tests/contract/fixtures/loop/positive/waveexecutionlooprun_min.json`
    - `tests/contract/fixtures/loop/negative/waveexecutionlooprun_missing_review_evidence.json`
  - Added deterministic policy checks and contract guards:
    - `tests/contract/check_loop_wave_execution_policy.py`
    - `tests/contract/check_loop_contract_docs.py`
    - `tests/contract/check_loop_schema_validity.py`
  - Registered contract checks in `tests/manifest.json` and synced `docs/testing/TEST_MATRIX.md`.
  - Independent AI-review closeout refreshed under isolated Stage-2 closeout scope:
    - `artifacts/reviews/20260306_stage2_active_plans_closeout_review_round2_prompt.md`
    - `artifacts/reviews/20260306_stage2_active_plans_closeout_review_round2_response.md`
- Verification summary:
  - `uv run --locked python tests/contract/check_loop_contract_docs.py` PASS
  - `uv run --locked python tests/contract/check_loop_schema_validity.py` PASS
  - `uv run --locked python tests/contract/check_loop_wave_execution_policy.py` PASS
  - `uv run --locked python tests/contract/check_test_registry.py` PASS
  - `uv run --locked python tests/contract/check_test_matrix_up_to_date.py` PASS
  - `uv run --locked python tests/run.py --profile core` PASS
  - `uv run --locked python tests/run.py --profile nightly` PASS
- Residual risks:
  - Provider-invoked `codex exec` may still hit transient environment stalls; retries and evidence capture remain required by closeout policy.
