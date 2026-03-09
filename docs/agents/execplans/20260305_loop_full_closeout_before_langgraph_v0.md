---
title: Master closeout plan - finish LOOP system and all active plans before LangChain/LangGraph adaptation
owner: Codex (local workspace)
status: done
created: 2026-03-05
---

## Purpose / Big Picture
This is the execution baseline we agreed on: do not start LangChain/LangGraph adaptation until the non-Lang baseline is fully converged, auditable, and robust. The plan first removes current blocking defects, then freezes framework-neutral contracts (the 21-item readiness set), then closes all active ExecPlans, and only then starts adapter work. Every stage must run as a LOOP-style execution with deterministic gates and independent AI review evidence.

## Glossary
- Stage 0: unblock current baseline (round6 FAIL + strict uv-only baseline).
- Stage 1: freeze 21 readiness items (4 contract domains x 5 hard artifacts + 1 replay invariant).
- Stage 2: close all active ExecPlans (LOOP and non-LOOP).
- Stage 3: full-system acceptance and evidence closeout.
- Stage 4: LangChain/LangGraph thin-adapter pilot.

## Scope
In scope:
- `tools/loop/**`, `tools/workflow/**` where required by gate/runtime hardening.
- `docs/contracts/**`, `docs/schemas/**`.
- `tests/contract/**`, `tests/e2e/**`, `tests/stress/**`, `tests/manifest.json`.
- `docs/testing/**`, `docs/setup/**` when deterministic generated docs must be refreshed.
- `docs/agents/execplans/**` status + retrospective updates.

Out of scope (until Stage 4):
- Introducing LangChain/LangGraph runtime as authoritative execution engine.
- Replacing deterministic gate logic with framework-native checks.

## Authoritative Inputs (By Stage)
Stage 0:
- `artifacts/reviews/20260305_loop_dirty_tree_gate_codex_exec_review_round6.md`
- `docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md`
- `docs/schemas/WaveExecutionLoopRun.schema.json`
- `tests/contract/check_uv_only_policy.py`

Stage 1:
- `docs/contracts/LOOP_GRAPH_CONTRACT.md`
- `docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md`
- `docs/contracts/LOOP_MCP_CONTRACT.md`
- `docs/contracts/LOOP_RUNTIME_CONTRACT.md`
- `docs/contracts/LOOP_PYTHON_SDK_CONTRACT.md`

Stage 2:
- `docs/agents/execplans/20260305_waveA_execution_meta_loop_v0.md`
- `docs/agents/execplans/20260305_loop_assurance_gate_and_review_history_v0.md`
- `docs/agents/execplans/20260305_loop_waveB_runtime_sdk_v0.md`
- `docs/agents/execplans/20260305_loop_waveC_hardening_backlog_v0.md`
- `docs/agents/execplans/20260304_formalization_experiment_productization_v0.md`
- `docs/agents/execplans/20260228_refactor_manifest_cache_topology.md`

Stage 3:
- `docs/agents/PLANS.md`
- `docs/contracts/TESTING_CONTRACT.md`
- `docs/contracts/DETERMINISM_CONTRACT.md`
- all updated stage artifacts/reviews.

Stage 4:
- Stage 0-3 outputs only (no new assumptions).

## 21-Item Readiness Freeze (Stage 1)
This plan freezes the following readiness set before framework adaptation:

1) Graph semantics contract domain (5 artifacts)
- state/decision table
- schema
- blocking gate rules
- min fixtures (1 positive + 3 negative)
- replay/determinism test

2) External reviewer invocation contract domain (5 artifacts)
- state/decision table
- schema
- blocking gate rules
- min fixtures (1 positive + 3 negative)
- replay/determinism test

3) Wave gate command policy contract domain (5 artifacts)
- state/decision table
- schema
- blocking gate rules
- min fixtures (1 positive + 3 negative)
- replay/determinism test

4) Third MCP contract domain (5 artifacts)
- state/decision table
- schema
- blocking gate rules
- min fixtures (1 positive + 3 negative)
- replay/determinism test

5) Global replay invariant (1 item)
- identical semantic input must preserve deterministic run identity and decision digest under replay/resume.

## Milestones
### 1) Stage 0 - Unblock baseline and enforce strict uv baseline
Deliverables:
- Fix all round6 findings, prioritizing both HIGH items first.
- Enforce strict uv execution baseline in gate/policy (and timeout evidence machine-checkability).
- Standardize `UV_CACHE_DIR` to writable workspace path for reviewer/tool runs.

Commands:
- `uv run --locked python tests/contract/check_loop_wave_blocking_gate.py`
- `uv run --locked python tests/contract/check_loop_schema_validity.py`
- `uv run --locked python tests/contract/check_loop_wave_execution_policy.py`
- `uv run --locked python tests/contract/check_uv_only_policy.py`
- `uv run --locked python tests/run.py --profile core`

Acceptance:
- No unresolved HIGH/MEDIUM findings for Stage 0 scope.
- Independent `codex exec` review verdict is PASS, or explicitly TRIAGED with reproducible blocker evidence.

### 2) Stage 1 - Freeze 21 readiness items
Deliverables:
- Contract/schema/gate/fixtures/tests for the 4 domains and global replay invariant.
- Deterministic acceptance checks integrated into contract suite.

Commands:
- `uv run --locked python tests/contract/check_loop_contract_docs.py`
- `uv run --locked python tests/contract/check_loop_schema_validity.py`
- `uv run --locked python tests/contract/check_loop_wave_execution_policy.py`
- `uv run --locked python tests/run.py --profile core`

Acceptance:
- All 21 items are machine-checkable (not text-only).
- No contract/schema drift across loop/runtime/wave/sdk/mcp docs.

### 3) Stage 2 - Close all active ExecPlans
Deliverables:
- Complete each active plan and set `status: done` with outcomes and verification evidence.
- Materialize missing Wave-C e2e/scenario/stress assets and advanced graph semantics coverage.

Commands:
- Plan-specific command sets from each active ExecPlan.
- `uv run --locked python tests/run.py --profile core`
- `uv run --locked python tests/run.py --profile nightly`

Acceptance:
- Active plan count is 0 for this closeout scope.
- Each closed plan has explicit PASS evidence or documented TRIAGED reason.

### 4) Stage 3 - Full-system acceptance and closeout report
Deliverables:
- Consolidated closeout report for baseline robustness before framework adaptation.
- Deterministic + AI-review evidence chain complete.
- LOOP-native test adaptation package (post-runtime freeze):
  - Add LOOP-path integration wrappers for `agent_eval` execution paths (`run_pack` / `run_scenario` and nightly real-agent entrypoints), so realistic eval tests emit LOOP runtime evidence.
  - Add LOOP-path integration wrappers for high-realism runners (`tests/e2e/run_cases.py`, `tests/e2e/run_scenarios.py`, `tests/stress/soak.py`) to cover sequence/pressure/soak under LOOP semantics.
  - Keep non-LOOP deterministic tests (schema/contract/unit) as a fast fault-isolation layer; LOOP tests are additive integration/soak gates, not replacements.
  - Refresh `tests/manifest.json` and generated matrix/docs after wrapper registration.

Commands:
- `uv run --locked python tests/e2e/run_cases.py --profile core`
- `uv run --locked python tests/e2e/run_scenarios.py --profile core`
- `uv run --locked python tests/stress/exec_soak_smoke.py`
- `uv run --locked python tests/stress/soak.py --iterations 1 --profile core`
- `uv run --locked python tests/run.py --profile core`
- `uv run --locked python tests/run.py --profile nightly`
- `uv run --locked python tools/tests/generate_test_matrix.py --write`

Acceptance:
- core/nightly/scenario/stress pass.
- Independent review for closeout scope reaches PASS.
- LOOP-path coverage exists for `agent_eval` + e2e/soak realistic runners and produces auditable LOOP artifacts.
- Non-LOOP deterministic baseline remains green (no loss of fault-isolation speed).

### 5) Stage 4 - Start LangChain/LangGraph pilot (thin adapter only)
Deliverables:
- Adapter pilot plan using existing deterministic kernel.
- No replacement of deterministic gate authority.

Commands:
- to be defined in a new Stage-4 ExecPlan after Stage 3 acceptance.

Acceptance:
- Adapter receives same inputs, produces equivalent decisions/evidence under replay checks.

## LOOP Execution Discipline For This Master Plan
- Every stage executes as: `PENDING -> RUNNING -> AI_REVIEW -> (repair loop) -> PASSED|TRIAGED`.
- Stage completion requires one of:
  - independent AI review PASS, or
  - explicit TRIAGED with reproducible blocker evidence.
- No silent closeout is allowed.

## Testing Plan (TDD)
- New/updated checks must fail first (red), then pass after implementation (green).
- For each stage, keep deterministic tests as merge blockers before any adapter work.
- Keep generated artifacts in non-authoritative paths and avoid polluting production libraries.

## Decision Log
- 2026-03-05: freeze sequence as Stage 0 -> Stage 1 -> Stage 2 -> Stage 3 -> Stage 4.
- 2026-03-05: no LangChain/LangGraph adaptation before complete baseline closeout.
- 2026-03-05: test strategy is dual-layer during closeout: keep deterministic non-LOOP unit/contract gates, and add LOOP-path integration/stress gates for realistic execution suites (`agent_eval`, e2e scenarios, soak/stress).

## Rollback Plan
- Revert only files touched in the current stage.
- Re-run stage acceptance commands to confirm rollback integrity.

## Outcomes & Retrospective (fill when done)
- Completed:
  - Stage 1 readiness freeze remains PASS (contract/schema/policy gates).
  - Stage 2 total closeout audit refreshed (2026-03-06):
    - active-plan check reconfirmed zero active plans
    - isolated independent `codex exec` review (`round3`) reached `VERDICT: PASS`
  - Stage 2 Wave-C hardening backlog closed:
    - missing e2e/scenario/stress assets materialized
    - graph merge semantics gate (`RACE`/`QUORUM`) added and passing
    - manifest/matrix synchronized
    - `run_scenarios` + two stress commands re-run with machine logs
    - isolated independent `codex exec` closeout review reached `VERDICT: PASS`
  - Stage 2 active-plan closure completed:
    - all Stage-2 active ExecPlans moved to `status: done`
    - non-LOOP formalization/refactor plans closed with verification evidence
  - Stage 3 full acceptance package completed:
    - `run_cases`/`run_scenarios`/`exec_soak_smoke`/`soak --profile core` refreshed with machine logs
    - core/nightly deterministic suites re-run under `uv run --locked`
    - matrix regenerated and up-to-date gate passing
    - one parallel `core/nightly` rerun attempt produced reproducible race failures (`no Plan.json` / telemetry clean collision); resolved by serial rerun policy with PASS evidence
- Verification summary:
  - `uv run --locked python tests/run.py --profile core` PASS
  - `uv run --locked python tests/run.py --profile nightly` PASS
  - `uv run --locked python tests/e2e/run_cases.py --profile core` PASS
  - `uv run --locked python tests/e2e/run_scenarios.py --profile core --lake-timeout-s 600 --step-timeout-s 600` PASS
  - `uv run --locked python tests/stress/exec_soak_smoke.py` PASS
  - `uv run --locked python tests/stress/soak.py --iterations 1 --profile core` PASS
  - `uv run --locked python tests/stress/loop_runtime_stress.py` PASS
  - `uv run --locked python tests/stress/loop_resource_contention_stress.py` PASS
  - `uv run --locked python tests/run.py --profile core` PASS (`artifacts/reviews/20260306_stage3_rerun_core_serial.log`)
  - `uv run --locked python tests/run.py --profile nightly` PASS (`artifacts/reviews/20260306_stage3_rerun_nightly_serial.log`)
  - Isolated closeout review PASS (`artifacts/reviews/20260306_stage2_total_closeout_review_round3_prompt.md`, `artifacts/reviews/20260306_stage2_total_closeout_review_round3_response.md`)
- Residual risks:
  - None blocking Stage 0-3 baseline closeout.
  - ExecPlan metadata hygiene debt exists in legacy docs without front-matter `status` (see `artifacts/reviews/20260306_execplan_status_inventory.json`); current active closure logic is unaffected (`active=0`, known non-done=0).
- Deferred:
  - Stage 4 LangChain/LangGraph thin-adapter pilot remains a follow-up after this baseline closeout plan.
