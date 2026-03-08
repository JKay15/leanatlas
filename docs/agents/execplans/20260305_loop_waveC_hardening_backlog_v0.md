---
title: LOOP Wave-C hardening backlog (e2e materialization + advanced graph semantics)
owner: Codex (local workspace)
status: done
created: 2026-03-05
---

## Purpose / Big Picture
Wave-B delivered runtime/SDK core and deterministic policy gates. Wave-C focuses on hardening gaps left explicitly as residual risks: materialized LOOP e2e/stress assets and stronger `RACE`/`QUORUM` semantics coverage with deterministic evidence.

## Scope
In scope:
- Materialize standalone LOOP e2e assets listed in Wave-B Milestone 6.
- Add stress runners for runtime and resource contention listed in Wave-B scope.
- Implement and test advanced `RACE`/`QUORUM` merge/winner semantics in `tools/loop/graph_runtime.py`.
- Add scenario coverage for graph semantics and exception/recovery interplay.

Out of scope:
- Third MCP service network packaging.
- Cross-repo extraction/split.

## Milestones
1) E2E/stress assets materialization
- Add missing files:
  - `tests/e2e/golden/core_loop_repair_success/case.yaml`
  - `tests/e2e/golden/core_loop_repair_exhausted/case.yaml`
  - `tests/e2e/golden/core_loop_audit_block_s1/case.yaml`
  - `tests/e2e/scenarios/scenario_loop_exception_recovery_chain/scenario.yaml`
  - `tests/e2e/scenarios/scenario_loop_resume_after_interrupt/scenario.yaml`
  - `tests/stress/loop_runtime_stress.py`
  - `tests/stress/loop_resource_contention_stress.py`

2) Graph semantics hardening
- Extend `tools/loop/graph_runtime.py` for deterministic `RACE`/`QUORUM` winner/arbitration semantics.
- Add contract tests for edge-kind specific behavior and tie-break determinism.

3) Full verification + independent review
- Run:
  - `uv run --locked python tests/e2e/run_cases.py --profile core`
  - `uv run --locked python tests/e2e/run_scenarios.py --profile core`
  - `uv run --locked python tests/stress/loop_runtime_stress.py`
  - `uv run --locked python tests/stress/loop_resource_contention_stress.py`
  - `uv run --locked python tests/run.py --profile core`
  - `uv run --locked python tests/run.py --profile nightly`
- Run independent `codex exec` review and persist prompt/response artifacts.

## Outcomes & retrospective (fill when done)
- Completed:
  - Materialized all Wave-C missing E2E/stress assets:
    - `tests/e2e/golden/core_loop_repair_success/**`
    - `tests/e2e/golden/core_loop_repair_exhausted/**`
    - `tests/e2e/golden/core_loop_audit_block_s1/**`
    - `tests/e2e/scenarios/scenario_loop_exception_recovery_chain/scenario.yaml`
    - `tests/e2e/scenarios/scenario_loop_resume_after_interrupt/scenario.yaml`
    - `tests/stress/loop_runtime_stress.py`
    - `tests/stress/loop_resource_contention_stress.py`
  - Added deterministic graph merge-semantics contract check:
    - `tests/contract/check_loop_graph_merge_semantics.py`
  - Registered new assets/tests in:
    - `tests/manifest.json`
    - `docs/testing/TEST_MATRIX.md`
  - Fixed stress workspace `run_id` collision in:
    - `tests/stress/soak.py` (`soak-<epoch>-<uuid8>`)
- Verification summary:
  - `uv run --locked python tests/e2e/validate_cases.py` PASS
  - `uv run --locked python tests/e2e/validate_scenarios.py` PASS
  - `uv run --locked python tests/contract/check_manifest_completeness.py` PASS
  - `uv run --locked python tests/contract/check_test_registry.py` PASS
  - `uv run --locked python tests/contract/check_loop_graph_merge_semantics.py` PASS
  - `uv run --locked python tests/contract/check_loop_dynamic_exception_entry_policy.py` PASS
  - `uv run --locked python tests/e2e/run_cases.py --profile core` PASS
  - `uv run --locked python tools/tests/generate_test_matrix.py --write` PASS
  - `uv run --locked python tests/contract/check_test_matrix_up_to_date.py` PASS
  - `uv run --locked python tests/run.py --profile core` PASS
  - `uv run --locked python tests/run.py --profile nightly` PASS
  - `uv run --locked python tests/e2e/run_scenarios.py --profile core --lake-timeout-s 600 --step-timeout-s 600` PASS
    - evidence: `artifacts/reviews/stage2_wavec_run_scenarios_core_20260306.log`
  - `uv run --locked python tests/stress/loop_runtime_stress.py` PASS
    - evidence: `artifacts/reviews/stage2_wavec_loop_runtime_stress_20260306.log`
  - `uv run --locked python tests/stress/loop_resource_contention_stress.py` PASS
    - evidence: `artifacts/reviews/stage2_wavec_loop_resource_contention_stress_20260306_rerun.log`
  - independent `codex exec` isolated closeout review: `VERDICT: PASS`
    - evidence: `artifacts/reviews/20260306_stage2_wavec_isolated_closeout_review_response.md`
- Residual risks:
  - `soak.py` `build_all_each_iter` now has deterministic `strict|observe_only` behavior; in mixed expected-status profiles (`core`) aggregate build non-zero becomes WARN in `observe_only` mode. This is intentional but should stay documented in stress semantics.
- Deferred:
  - none
