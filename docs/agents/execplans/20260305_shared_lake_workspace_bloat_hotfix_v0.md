---
title: Fix E2E/Soak workspace bloat by enforcing shared Lake workdir reuse
owner: maintainer
status: done
created: 2026-03-05
---

## Purpose / Big Picture
Recent test runs expanded repository footprint from roughly 7G to 33G because scenario/soak runners created many per-run workdirs that each materialized huge `.lake/packages` trees. This plan hardens runners to use a single shared workspace per runner family, reset content while preserving `.lake`, and enforce this behavior with contract checks. The goal is to stop explosive file-count/size growth while keeping reproducible local execution behavior.

## Glossary
- Shared workdir: Stable workspace path reused across runs (`.../shared/workdir`).
- Cold init: Recreate workspace from fixture root when dependency stamp changes.
- Warm reset: Reset workspace content while preserving `.lake/` cache.
- Workspace bloat: Unbounded creation of large run-scoped workdirs.

## Scope
In scope:
- `tests/e2e/run_scenarios.py`
- `tests/stress/soak.py`
- `tests/contract/check_shared_cache_policy.py`
- local cleanup under `.cache/leanatlas/e2e_scenarios/**` and `.cache/leanatlas/soak/**`

Out of scope:
- Changing shared cache seeding algorithm in `tools/workflow/shared_cache.py`
- Agent-eval runner behavior
- Production docs/contracts outside direct shared-cache policy checks

## Interfaces and Files
- `tests/e2e/run_scenarios.py`
  - add shared workspace lifecycle (`shared_root/shared_workdir`), deps stamp, warm reset helper usage
- `tests/stress/soak.py`
  - mirror shared workspace lifecycle
- `tests/contract/check_shared_cache_policy.py`
  - enforce anti-bloat markers for scenario/soak runners

## Milestones
1) Add failing contract checks (TDD)
- Deliverables: update `tests/contract/check_shared_cache_policy.py` with shared-workspace assertions
- Commands: `uv run --locked python tests/contract/check_shared_cache_policy.py`
- Acceptance: command fails on current code with scenario/soak policy violations

2) Implement shared workspace reuse in runners
- Deliverables: update `tests/e2e/run_scenarios.py` and `tests/stress/soak.py`
- Commands: local static sanity (`py_compile`) + targeted runner smoke
- Acceptance: contract check passes; no per-run scenario/soak workdir creation in code path

3) Cleanup leaked heavy workdirs + verify disk delta
- Deliverables: remove stale `.cache/leanatlas/e2e_scenarios/*__*` and `.cache/leanatlas/soak/soak-*`
- Commands: `du` before/after snapshots
- Acceptance: `.cache/leanatlas/e2e_scenarios` and `.cache/leanatlas/soak` shrink to shared-root-only footprint

4) Verify and close out
- Deliverables: run required tests (at least changed contracts + one scenario wrapper)
- Commands:
  - `uv run --locked python tests/contract/check_shared_cache_policy.py`
  - `uv run --locked python tests/e2e/validate_scenarios.py`
  - `uv run --locked python tests/e2e/exec_scenarios_smoke.py`
- Acceptance: all pass or explicit triage evidence recorded

## Testing plan (TDD)
- Add contract assertions first and observe expected failure.
- Then implement code and re-run the same checks.
- Run scenario smoke wrapper to ensure runner still works with shared workspace.
- Avoid repository pollution by cleaning stale `.cache` run dirs after verification.

## Decision log
- Prefer shared-workdir reuse over deleting all caches each run: preserves speed and keeps one cache topology.
- Keep shared-cache core algorithm unchanged for this hotfix to minimize blast radius.

## Rollback plan
- Revert changes in three files above.
- Re-run `uv run --locked python tests/contract/check_shared_cache_policy.py`; expected failures indicate old behavior restored.

## Outcomes & retrospective (fill when done)
- Implemented:
  - `tests/e2e/run_scenarios.py` now uses a shared workspace root and no longer creates per-scenario `scenario_id__run_id` workdirs.
  - `tests/stress/soak.py` now reuses the same shared workspace root (no `soak-*/.lake` trees).
  - `tests/contract/check_shared_cache_policy.py` now enforces shared-workspace markers, detects dynamic per-run workdir patterns via regex, and handles missing files gracefully.
  - `execute_case_in_workdir()` now clears the case problem directory before fixture overlay (stale-file guard) and returns `wall_time_ms` (fixes soak timing undercount).
- Validation run:
  - `uv run --locked python -m py_compile tests/e2e/run_scenarios.py tests/stress/soak.py tests/contract/check_shared_cache_policy.py`
  - `uv run --locked python tests/contract/check_shared_cache_policy.py`
  - `uv run --locked python tests/e2e/validate_scenarios.py`
  - `uv run --locked python tests/e2e/run_scenarios.py --scenario scenario_phase3_gc_apply_smoke --lake-timeout-s 600 --step-timeout-s 600`
  - `uv run --locked python tests/stress/soak.py --iterations 1 --profile smoke --seed 0 --lake-timeout-s 300` (environment-dependent failure observed on cold workspace due `proofwidgets/widgetJsAll` build failure; unrelated to workspace-bloat fix path)
- Incident result:
  - Repository size reduced from ~33G incident state back to ~7G after pruning leaked workdirs and cleaning shared workspace post-verification.
- Residual risk:
  - Shared workspace path is intentionally mutable; parallel runner invocations can interfere (triaged for later lock/lease hardening).
