---
title: Close stale active execplans after LOOP hardening
owner: codex
status: done
created: 2026-03-06
---

## Purpose / Big Picture
The 2026-03-06 LOOP hardening work already landed and was committed, but two follow-up ExecPlans still advertise `status: active` even though their outcomes are either fully implemented or already superseded by later rounds. That leaves plan bookkeeping out of sync with the actual repository state and makes it harder to tell which work is still live. This cleanup closes that gap. The goal is narrow: update the stale plan records, add a small contract check that prevents these specific stale-active cases from reappearing unnoticed, and verify that the repository remains green after the bookkeeping cleanup.

## Glossary
- stale active execplan: an ExecPlan whose tracked work is already completed or superseded, but whose front matter still says `status: active`.
- closeout hygiene: keeping plan status and outcomes aligned with the actual implementation state.

## Scope
In scope:
- `docs/agents/execplans/20260306_maintainer_loop_visibility_wait_policy_v0.md`
- `docs/agents/execplans/20260306_review_runner_semantic_idle_v0.md`
- a small deterministic contract check for stale plan-status hygiene
- manifest/test-matrix updates required by the new check

Out of scope:
- new LOOP runtime or provider changes
- revisiting the remaining semantic-progress narrowing debt
- modifying older non-20260306 execplans

## Interfaces and Files
- `docs/agents/execplans/20260306_execplan_closeout_hygiene_v0.md`
  - this plan and execution record
- `docs/agents/execplans/20260306_maintainer_loop_visibility_wait_policy_v0.md`
  - set the final status and fill the outcomes section
- `docs/agents/execplans/20260306_review_runner_semantic_idle_v0.md`
  - set the final status and make the retrospective explicit about what is done vs. what debt remains elsewhere
- `tests/contract/check_execplan_closeout_hygiene.py`
  - assert the two stale plans are no longer left `active` / `Pending`
- `tests/manifest.json`
  - register the new contract test

## Milestones
1) Red test for stale active plans
- Deliverables:
  - add `tests/contract/check_execplan_closeout_hygiene.py`
  - update `tests/manifest.json`
- Commands:
  - `uv run --locked python tests/contract/check_execplan_closeout_hygiene.py`
- Acceptance:
  - the new check fails before plan records are updated because the two target plans are still `active` or still say `Pending`.

2) Close the stale plan records
- Deliverables:
  - update `docs/agents/execplans/20260306_maintainer_loop_visibility_wait_policy_v0.md`
  - update `docs/agents/execplans/20260306_review_runner_semantic_idle_v0.md`
- Commands:
  - `uv run --locked python tests/contract/check_execplan_closeout_hygiene.py`
- Acceptance:
  - both plans stop advertising stale active/pending state
  - the semantic-progress narrowing debt remains recorded, but as a follow-up debt rather than an active status mismatch

3) Verification and closeout
- Deliverables:
  - fill outcomes in this plan
- Commands:
  - `uv run --locked python tests/contract/check_execplan_closeout_hygiene.py`
  - `uv run --locked python tests/run.py --profile core`
  - `lake build`
  - `git diff --check`
- Acceptance:
  - hygiene check passes
  - core and build stay green
  - this bookkeeping cleanup has a maintainer LOOP closeout artifact

## Testing plan (TDD)
- Add `tests/contract/check_execplan_closeout_hygiene.py`.
- Before editing the target plans, require the new check to fail on the stale `status: active` / `- Pending.` cases.
- Keep the check deterministic and limited to the two known 2026-03-06 plans this cleanup is closing.

## Decision log
- 2026-03-06: treat stale plan status as contract debt worth testing, not just prose cleanup.
- 2026-03-06: keep the hygiene check intentionally narrow to the known stale LOOP hardening plans rather than enforcing a repo-wide policy with unclear edge cases.

## Rollback plan
- Revert:
  - `docs/agents/execplans/20260306_execplan_closeout_hygiene_v0.md`
  - `docs/agents/execplans/20260306_maintainer_loop_visibility_wait_policy_v0.md`
  - `docs/agents/execplans/20260306_review_runner_semantic_idle_v0.md`
  - `tests/contract/check_execplan_closeout_hygiene.py`
  - `tests/manifest.json`
- Re-run:
  - `uv run --locked python tests/contract/check_execplan_closeout_hygiene.py`

## Outcomes & retrospective (fill when done)
- Outcome: `PASSED`
- What changed:
  - added `tests/contract/check_execplan_closeout_hygiene.py` so the two stale 2026-03-06 LOOP plans cannot stay `active` / `Pending` unnoticed
  - updated `docs/agents/execplans/20260306_maintainer_loop_visibility_wait_policy_v0.md` to record that its work landed through later split follow-up plans
  - updated `docs/agents/execplans/20260306_review_runner_semantic_idle_v0.md` to mark the plan complete while keeping the later semantic-progress debt explicitly tracked as follow-up work
  - updated `tests/manifest.json` and regenerated `docs/testing/TEST_MATRIX.md`
- Verification:
  - `uv run --locked python tests/contract/check_execplan_closeout_hygiene.py` PASS
  - `uv run --locked python tests/run.py --profile core` PASS
  - `lake build` PASS
  - `git diff --check` PASS
- Maintainer LOOP evidence for this cleanup:
  - run key: `0f8a0e9febbb067bde7e68ba671a17c734d9a5087bf3e1ac59a4fcdd246ae6df`
  - session: `artifacts/loop_runtime/by_key/0f8a0e9febbb067bde7e68ba671a17c734d9a5087bf3e1ac59a4fcdd246ae6df/graph/MaintainerSession.json`
  - progress: `artifacts/loop_runtime/by_key/0f8a0e9febbb067bde7e68ba671a17c734d9a5087bf3e1ac59a4fcdd246ae6df/graph/MaintainerProgress.json`
  - summary: `artifacts/loop_runtime/by_key/0f8a0e9febbb067bde7e68ba671a17c734d9a5087bf3e1ac59a4fcdd246ae6df/graph/GraphSummary.jsonl`
- Retrospective:
  - the main bug was not missing implementation; it was stale plan bookkeeping after the work had already been split and completed
  - registering a narrow hygiene check is cheaper than repeatedly rediscovering stale active plans during later audits
