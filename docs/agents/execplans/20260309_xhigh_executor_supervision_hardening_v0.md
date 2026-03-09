---
title: Harden xhigh executor supervision so parent LOOP uses reminder-first bounded triage
owner: Codex (local workspace)
status: done
created: 2026-03-09
parent_execplan: docs/agents/execplans/20260307_loop_core_parallel_nested_batch_v0.md
---

## Purpose / Big Picture
The current LOOP parent-supervisor path is good enough for deterministic child-wave orchestration, but it is too aggressive when the child executor is intentionally running with `xhigh` reasoning. In practice, an `xhigh` implementation child may spend early time rebuilding context because it cannot inherit hidden maintainer state. The current supervisor path does not encode that allowance, and a human supervisor can incorrectly treat that behavior as drift and stop the child before it has received any explicit follow-up guidance.

This plan hardens that gap in a bounded way. The repair does not change reviewer policy and does not add new productization themes. Instead, it teaches the parent LOOP system to treat early `xhigh` context rebuild as an allowed progress class, to publish known conclusions and non-goals as explicit supervisor guidance evidence, to rematerialize that guidance into downstream context packs, and to require a reminder-first retry before final triage when there is repeated no-milestone drift. The goal is to prevent a repeat of the recent phase-1 supervision mistake without pretending that the runtime already owns a fully interactive live-PTY follow-up protocol.

## Glossary
- xhigh executor: an implementation child wave whose execution lane intentionally uses high reasoning effort.
- early context rebuild: the initial analysis period where an executor re-reads local docs/code because it cannot see hidden prior maintainer reasoning.
- milestone progress: explicit evidence that the child has moved beyond context rebuild into bounded task progress, such as test edits, patch application, targeted check execution, or other machine-declared milestones.
- supervisor guidance: append-only parent evidence that records known conclusions, non-goals, and reminder instructions for the child.
- reminder-first triage: a policy where the parent publishes follow-up guidance and rematerializes context before declaring repeated no-progress drift terminal.

## Scope
In scope:
- `tools/loop/batch_supervisor.py`
- `tools/loop/publication.py`
- `tools/loop/__init__.py`
- targeted contract tests for batch supervision/publication/runtime docs
- LOOP contracts/docs that describe supervisor guidance and reminder-first triage
- maintainer LOOP materialization and bounded closeout for this repair wave

Out of scope:
- changing reviewer tier policy (`FAST + low`, bounded `medium`)
- adding `xhigh` back to reviewer closeout
- fully interactive provider-specific live stdin follow-up for long-running child sessions
- new worktree/autopilot themes unrelated to this supervision gap

## Interfaces and Files
- `tools/loop/publication.py`
  - add an explicit supervisor-guidance event surface for known conclusions / non-goals / reminder text
  - extend rematerialized context packs so downstream child attempts can prove they consumed that guidance
- `tools/loop/batch_supervisor.py`
  - add a bounded supervision policy for retryable xhigh executor drift
  - allow early context rebuild without immediate triage
  - require reminder publication + rematerialization before final no-progress triage
- `tools/loop/__init__.py`
  - export any new public helper surfaces used by generic LOOP callers
- `tests/contract/check_loop_publication_runtime.py`
  - add deterministic coverage for supervisor-guidance publication and context-pack inclusion
- `tests/contract/check_loop_batch_supervisor.py`
  - add deterministic coverage for reminder-first retry, allowed early context rebuild, and repeated no-milestone triage
- `docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md`
- `docs/contracts/LOOP_PYTHON_SDK_CONTRACT.md`
- `tests/contract/check_loop_contract_docs.py`
- `tests/contract/check_loop_python_sdk_contract_surface.py`
  - sync contract language and SDK-facing surface assertions

## Milestones
### M1. Freeze the bounded hardening scope and materialize maintainer session
Deliverables:
- this ExecPlan
- a materialized maintainer LOOP session for the bounded supervision repair

Commands:
- `sed -n '1,240p' docs/agents/execplans/20260309_xhigh_executor_supervision_hardening_v0.md`
- `python - <<'PY' ... materialize MaintainerLoopSession ... PY`

Acceptance:
- the plan explicitly keeps reviewer policy unchanged
- maintainer session artifacts exist before implementation begins

### M2. Add TDD coverage for reminder-first xhigh supervision
Deliverables:
- expanded `tests/contract/check_loop_batch_supervisor.py`
- expanded `tests/contract/check_loop_publication_runtime.py`
- any targeted contract-doc assertions needed for the new semantics

Commands:
- `uv run --locked python tests/contract/check_loop_batch_supervisor.py`
- `uv run --locked python tests/contract/check_loop_publication_runtime.py`
- `uv run --locked python tests/contract/check_loop_contract_docs.py`
- `uv run --locked python tests/contract/check_loop_python_sdk_contract_surface.py`

Acceptance:
- tests fail before implementation because supervisor guidance/reminder-first retry is not yet implemented

### M3. Implement bounded supervisor-guidance and no-milestone policy
Deliverables:
- updated `publication.py`
- updated `batch_supervisor.py`
- synced public exports/docs

Commands:
- `uv run --locked python tests/contract/check_loop_batch_supervisor.py`
- `uv run --locked python tests/contract/check_loop_publication_runtime.py`
- `uv run --locked python tests/contract/check_loop_contract_docs.py`
- `uv run --locked python tests/contract/check_loop_python_sdk_contract_surface.py`

Acceptance:
- supervisor guidance is append-only and explicit
- rematerialized context packs can carry supervisor guidance refs
- early context rebuild does not trigger immediate triage
- repeated no-milestone drift requires reminder publication before terminal triage

### M4. Verify full repo state and close under low/medium reviewer policy
Deliverables:
- passing final verification on the current byte state
- fresh maintainer AI review closeout under the committed reviewer policy only

Commands:
- `uv run --locked python tests/run.py --profile core`
- `uv run --locked python tests/run.py --profile nightly`
- `lake build`
- `git diff --check`

Acceptance:
- targeted checks pass
- `core`, `nightly`, `lake build`, and `git diff --check` pass
- closeout uses low/medium reviewer policy or explicit tooling triage evidence, never `xhigh`

## Testing plan (TDD)
- Extend `tests/contract/check_loop_publication_runtime.py` to require:
  - deterministic `SUPERVISOR_GUIDANCE` event artifacts
  - preserved `known_conclusion_refs`
  - preserved `non_goal_refs`
  - rematerialized context packs that cite supervisor guidance explicitly
- Extend `tests/contract/check_loop_batch_supervisor.py` to require:
  - retryable `CONTEXT_REBUILD` updates do not immediately triage a child
  - retryable `NO_MILESTONE_PROGRESS` updates publish a reminder and rematerialize context before retry
  - terminal triage only occurs after repeated no-milestone drift exhausts the configured budget
  - integrated closeout preserves the reminder/guidance lineage in child results
- Keep all tests deterministic by using inline callable executors rather than live provider calls

## Decision log
- This repair hardens parent supervision at the attempt/rematerialization level instead of implementing a provider-specific live stdin follow-up channel.
- Reviewer policy remains unchanged; the repair applies to execution supervision only.
- Supervisor guidance must be explicit append-only evidence, not hidden maintainer memory.

## Rollback plan
- Revert changes in:
  - `tools/loop/publication.py`
  - `tools/loop/batch_supervisor.py`
  - `tools/loop/__init__.py`
  - targeted test/doc files
- Re-run:
  - `uv run --locked python tests/contract/check_loop_batch_supervisor.py`
  - `uv run --locked python tests/contract/check_loop_publication_runtime.py`
  - `uv run --locked python tests/run.py --profile core`
  - `lake build`

## Outcomes & retrospective (fill when done)
- Implemented bounded parent-supervisor hardening for `xhigh` executor lanes:
  - explicit `SUPERVISOR_GUIDANCE` publication plus rematerialized follow-up context
  - early `CONTEXT_REBUILD` handled as bounded retryable progress rather than immediate terminal drift
  - reminder-first retry before terminal `NO_MILESTONE_PROGRESS` triage
  - deterministic `looplib` standalone export for `publish_supervisor_guidance_event(...)`
  - idempotent `materialize_batch_supervisor(...)` so rematerializing the same frozen run no longer resets state
  - default `allow_context_rebuild_retries = 1` so the documented `xhigh` context-rebuild path works without per-caller opt-in
- Verification passed on the final byte state:
  - targeted contract checks
  - `uv run --locked python tests/run.py --profile core`
  - `uv run --locked python tests/run.py --profile nightly`
  - `lake build`
  - `git diff --check`
- Fresh `medium` AI review discovered and drove two real fixes:
  - `looplib` export drift for `publish_supervisor_guidance_event(...)`
  - non-idempotent rematerialization resetting existing batch state
- Final-byte-state reviewer closeout ended as tooling-triaged rather than clean `REVIEW_RUN`:
  - round 5 was invalidated by nested provider-event text pulled from required-context stdout artifacts
  - round 6 removed those nested stdout refs but hit provider stream-disconnect / command-failure tooling
  - authoritative evidence: `artifacts/reviews/20260309_xhigh_executor_supervision_hardening_review_round6_medium_summary.json`
