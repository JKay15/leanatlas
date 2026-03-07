---
title: Add a stable maintainer closeout ref so ExecPlans can cite settled-state LOOP closeout without run-key recursion
owner: Codex (local workspace)
status: active
created: 2026-03-07
parent_execplan: docs/agents/execplans/20260307_loop_core_parallel_nested_batch_v0.md
---

## Purpose / Big Picture
Maintainer LOOP closeout is currently persisted only under run-key-specific artifact paths such as `artifacts/loop_runtime/by_key/<run_key>/graph/GraphSummary.jsonl`. That works for graph replay, but it creates a bookkeeping recursion for ExecPlans: the plan file contributes to maintainer session run identity via `execplan_hash`, while the plan body also wants to cite the final settled-state closeout artifact. If the plan tries to inline a run-key-specific closeout path after the last edit, that citation changes the plan bytes and therefore changes the final run key again. This blocker is now actively preventing `20260307_review_orchestration_automation_v0.md` from being honestly closed as `done`. This plan introduces a stable, execplan-addressable closeout ref artifact so plans can cite authoritative settled-state LOOP closeout without self-referential run-key drift.

## Scope
In scope:
- stable maintainer closeout ref artifact written at closeout time under a path keyed by `execplan_ref`, not by `run_key`
- maintainer/session API changes needed to persist and expose that ref
- contract/doc updates describing how ExecPlans should cite settled-state closeout
- deterministic tests for closeout ref persistence and replay behavior

Out of scope:
- redesigning maintainer run identity to exclude `execplan_hash`
- changing reviewer/provider behavior
- finishing all remaining child plans in the batch

## Interfaces and Files
- `tools/loop/maintainer.py`
- `tools/loop/__init__.py` (if a new helper/export is needed)
- `docs/agents/PLANS.md`
- `docs/contracts/LOOP_PYTHON_SDK_CONTRACT.md`
- `tests/contract/check_loop_maintainer_session.py`
- `tests/contract/check_loop_contract_docs.py`
- `tests/contract/check_loop_python_sdk_contract_surface.py`
- `docs/agents/execplans/20260307_review_orchestration_automation_v0.md`

New stable artifact target:
- `artifacts/loop_runtime/by_execplan/<stable_execplan_id>/MaintainerCloseoutRef.json`

Minimum payload expectation:
- `execplan_ref`
- `run_key`
- `summary_ref`
- `final_status`
- `updated_at_utc`

## Milestones
1) Red tests for stable closeout refs
- Deliverables:
  - extend `check_loop_maintainer_session.py` to require a stable execplan-addressable closeout ref after maintainer closeout
  - extend contract/doc surface checks to require wording about the stable closeout ref
- Commands:
  - `uv run --locked python tests/contract/check_loop_maintainer_session.py`
  - `uv run --locked python tests/contract/check_loop_contract_docs.py`
  - `uv run --locked python tests/contract/check_loop_python_sdk_contract_surface.py`
- Acceptance:
  - tests fail before implementation because no stable closeout ref exists yet

2) Persist execplan-addressable settled-state closeout
- Deliverables:
  - update `maintainer.py` so closing a maintainer session writes/updates `MaintainerCloseoutRef.json`
  - keep the path stable across post-closeout documentation edits that do not change the execplan pathname
- Commands:
  - `uv run --locked python tests/contract/check_loop_maintainer_session.py`
- Acceptance:
  - a plan can cite a stable closeout ref path without embedding a run-key-specific path in its own body

3) Document the authoritative citation path
- Deliverables:
  - update `docs/agents/PLANS.md`
  - update `docs/contracts/LOOP_PYTHON_SDK_CONTRACT.md`
  - revise `20260307_review_orchestration_automation_v0.md` to cite the stable closeout ref once available
- Commands:
  - `uv run --locked python tests/contract/check_loop_contract_docs.py`
  - `uv run --locked python tests/contract/check_loop_python_sdk_contract_surface.py`
- Acceptance:
  - plan closeout guidance now explains how to cite settled-state maintainer closeout without recursive run-key drift

4) Verification and blocker closeout
- Deliverables:
  - rerun required verification for the maintainer/LOOP surfaces
  - close the blocker by updating `20260307_review_orchestration_automation_v0.md` to a truthful final state
- Commands:
  - `uv run --locked python tests/run.py --profile core`
  - `uv run --locked python tests/run.py --profile nightly`
  - `lake build`
  - `git diff --check`
- Acceptance:
  - the blocker plan lands with passing verification
  - `20260307_review_orchestration_automation_v0.md` can honestly cite settled-state closeout and move to `status: done`

## Testing plan (TDD)
- Extend `tests/contract/check_loop_maintainer_session.py` so a closed maintainer session must emit:
  - run-key-specific `GraphSummary.jsonl`
  - stable `MaintainerCloseoutRef.json`
- Cover replay/rematerialization behavior so reloading a closed session preserves the same stable closeout ref instead of drifting or disappearing.
- Update contract-surface tests so the stable closeout ref path becomes mandatory in docs.

## Decision log
- 2026-03-07: fixing ExecPlan closeout recursion is a prerequisite for trustworthy staged-batch automation; otherwise plans that change their own status/outcomes cannot stably cite maintainer LOOP closeout.
- 2026-03-07: prefer a stable execplan-addressable alias/ref over removing `execplan_hash` from maintainer run identity; the latter would weaken determinism.

## Rollback plan
- Revert:
  - `tools/loop/maintainer.py`
  - any new helper/export
  - updated contract/docs/tests
  - final closeout-ref citation edits in affected ExecPlans
- Re-run:
  - `uv run --locked python tests/contract/check_loop_maintainer_session.py`
  - `uv run --locked python tests/run.py --profile core`

## Outcomes & retrospective (fill when done)
- Completed:
- Verification:
- Residual risks:
- Follow-on recommendation:
