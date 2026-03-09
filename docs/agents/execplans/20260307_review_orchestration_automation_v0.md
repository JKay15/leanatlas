---
title: Compile staged review acceleration into executable LOOP review orchestration
owner: Codex (local workspace)
status: done
created: 2026-03-07
parent_execplan: docs/agents/execplans/20260307_loop_core_parallel_nested_batch_v0.md
---

## Purpose / Big Picture
The repository already has deterministic staged-review planning helpers under `tools/loop/review_strategy.py`, but they still stop at plan generation. That leaves the new native `PARALLEL` / `NESTED` core without a committed high-value scenario, and it leaves review acceleration as a maintainer convention rather than an executable LOOP composition. This wave compiles staged narrowing and pyramid-review plans into a real LOOP review-orchestration subgraph with auditable graph/bundle artifacts.

## Scope
In scope:
- executable review-orchestration graph/bundle builders on top of `build_pyramid_review_plan(...)`
- deterministic tests for graph materialization and runtime evidence
- SDK/contract docs for the orchestration helper surface

Out of scope:
- live provider execution automation for every review stage
- reviewer supersession/reconciliation runtime beyond graph/bundle materialization
- worktree orchestration and operator/maintainer workflow wiring

## Interfaces and Files
- `tools/loop/review_orchestration.py`
- `tools/loop/__init__.py`
- `docs/contracts/LOOP_PYTHON_SDK_CONTRACT.md`
- `docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md`
- `tests/contract/check_loop_review_orchestration.py`

## Milestones
1) Red tests for executable review orchestration
- add `tests/contract/check_loop_review_orchestration.py`
- update contract-surface checks for new helper exports and contract wording

2) Compile strategy plans into LOOP graph/bundle artifacts
- materialize fast partition scan as fan-out review nodes
- materialize deep follow-up as nested child-review nodes
- keep final integrated closeout as the only closeout-authoritative review stage

3) Contracts/docs/exports
- export orchestration helpers from `tools.loop`
- document the helper surface and resulting graph semantics

4) Verification and closeout
- targeted contract checks
- `uv run --locked python tests/run.py --profile core`
- `uv run --locked python tests/run.py --profile nightly`
- `lake build`
- `git diff --check`

## Decision log
- 2026-03-07: use review orchestration as the first committed high-value `NESTED` scenario instead of keeping nested execution dormant.
- 2026-03-07: keep orchestration metadata in a sidecar bundle so `LoopGraphSpec` stays schema-clean.
- 2026-03-07: final integrated closeout remains authoritative; partition-local rounds are not.

## Outcomes & retrospective (fill when done)
- Completed:
  - committed executable review-orchestration helpers in [review_orchestration.py](/Users/xiongjiangkai/xjk_papers/leanatlas/tools/loop/review_orchestration.py) on top of [review_strategy.py](/Users/xiongjiangkai/xjk_papers/leanatlas/tools/loop/review_strategy.py)
  - materialized `FAST` partition fan-out, `DEEP` nested follow-up, and an authoritative integrated `MEDIUM` closeout by default, with explicit `STRICT` exception closeout support, as a deterministic bundle/graph surface
  - exported the orchestration helpers from [tools/loop/__init__.py](/Users/xiongjiangkai/xjk_papers/leanatlas/tools/loop/__init__.py)
  - tightened authoritative replay invariants so compilation now rejects:
    - malformed or non-canonical helper-derived `partition_id` values
    - repartitioned helper scopes under canonical-looking ids
    - narrowed plans that forge `FULL_SCOPE_AFTER_EMPTY_FOLLOWUP`
    - non-integer `partitioning_policy.max_files_per_partition` replays that would fork `strategy_fingerprint`
  - aligned [LOOP_PYTHON_SDK_CONTRACT.md](/Users/xiongjiangkai/xjk_papers/leanatlas/docs/contracts/LOOP_PYTHON_SDK_CONTRACT.md) and contract-surface tests with the executable orchestration surface
- Verification:
  - targeted checks:
    - `uv run --locked python tests/contract/check_loop_review_strategy.py`
    - `uv run --locked python tests/contract/check_loop_review_orchestration.py`
    - `uv run --locked python tests/contract/check_loop_contract_docs.py`
    - `uv run --locked python tests/contract/check_loop_python_sdk_contract_surface.py`
  - full verification on the final code/docs/tests state:
    - `uv run --locked python tests/run.py --profile core`
    - `uv run --locked python tests/run.py --profile nightly`
    - `lake build`
    - `git diff --check`
  - historical implementation-wave artifacts from the initial 2026-03-07 landing (superseded as settled-state evidence for current bytes once later replay/policy repairs changed the scoped files):
    - [round25](/Users/xiongjiangkai/xjk_papers/leanatlas/artifacts/verify/20260307_review_orchestration_automation_v0_verify_round25.md)
    - [round46 prompt](/Users/xiongjiangkai/xjk_papers/leanatlas/artifacts/reviews/20260307_review_orchestration_automation_review_round46_strict_prompt.md)
    - [round46 response](/Users/xiongjiangkai/xjk_papers/leanatlas/artifacts/reviews/20260307_review_orchestration_automation_review_round46_strict_response.md)
    - [initial-wave MaintainerCloseoutRef.json](/Users/xiongjiangkai/xjk_papers/leanatlas/artifacts/loop_runtime/by_execplan/docs__agents__execplans__20260307_review_orchestration_automation_v0.md__62646d9128b5/MaintainerCloseoutRef.json)
  - current post-landing authoritative status is tracked through later revalidation/repair work rather than the initial-wave closeout:
    - [20260308_xhigh_revalidation_matrix_v0.md](/Users/xiongjiangkai/xjk_papers/leanatlas/docs/agents/execplans/20260308_xhigh_revalidation_matrix_v0.md)
    - [20260308_xhigh_revalidation_repair_wave_v0.md](/Users/xiongjiangkai/xjk_papers/leanatlas/docs/agents/execplans/20260308_xhigh_revalidation_repair_wave_v0.md)
- Residual risks:
  - live provider execution automation for every review stage is still out of scope; this plan only compiled the deterministic orchestration/bundle layer
  - reviewer supersession/reconciliation runtime remains follow-on work under the batch master plan
- Follow-on recommendation:
  - continue with the next staged batch theme from the master plan: turn the deterministic orchestration helpers into default/automated review execution, then add capability publish/context refresh so downstream loops can adopt newly published review capabilities without manual handoff
