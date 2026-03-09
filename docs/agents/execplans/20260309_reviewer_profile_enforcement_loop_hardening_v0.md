---
title: Harden LOOP reviewer-runtime profile enforcement so closeout reviews fail closed on provider mismatch
owner: Codex (local workspace)
status: active
created: 2026-03-09
parent_execplan: docs/agents/execplans/20260307_loop_core_parallel_nested_batch_v0.md
---

## Purpose / Big Picture
LeanAtlas already documents a tiered reviewer policy: implementation/execution work may use stronger reasoning when needed, but maintainer closeout reviews must stay on the committed reviewer lane of `FAST + low` with bounded `medium` escalation. That policy is currently only enforced at the prompt/declared-input layer. In practice, the provider can launch a different reviewer runtime than requested, and the current closeout runner will still accept the result if it gets a terminal response.

This plan hardens that gap using the existing LOOP automation path instead of manual discipline. The end state is: reviewer runtime metadata is captured from provider evidence, the maintainer review runner compares actual provider launch metadata against the allowed reviewer lane, and any mismatch fails closed with explicit evidence. Execution/implementation nodes may still use `xhigh`; the new hardening applies only to maintainer AI-review closeout lanes and review-orchestration helpers that automate those lanes.

## Glossary
- reviewer lane: the AI-review/closeout path that must obey the committed policy of `low` baseline with bounded `medium` escalation.
- execution lane: implementation or maintainer execution work; it may still use `xhigh`.
- actual runtime metadata: provider-observed launch data such as `model`, `provider`, and `reasoning effort`, extracted from command stdout/stderr evidence rather than trusting the prompt declaration.
- profile mismatch: any case where the provider runtime launches outside the allowed reviewer lane for the requested review round.

## Scope
In scope:
- `tools/loop/review_canonical.py`
- `tools/loop/review_runner.py`
- `tools/loop/review_orchestration.py`
- targeted contract tests under `tests/contract/**`
- LOOP contracts/docs that describe reviewer-tier enforcement
- a bounded maintainer ExecPlan closeout review for this hardening delta

Out of scope:
- changing default reviewer policy tiers themselves
- changing execution/implementation lane model usage
- new xhigh automation or reviewer-effectiveness experiments
- unrelated phase-1 external split work

## Interfaces and Files
- `tools/loop/review_canonical.py`
  - parse provider runtime banner metadata from provider evidence
  - persist canonical runtime metadata for each attempt
- `tools/loop/review_runner.py`
  - accept reviewer-runtime policy expectations
  - fail closed when actual provider runtime violates allowed reviewer profiles
- `tools/loop/review_orchestration.py`
  - pass explicit reviewer-runtime expectations into automated review stages
- `tests/contract/check_loop_review_runner.py`
  - add regression cases for provider/runtime mismatch vs allowed reviewer lane
- `tests/contract/check_loop_contract_docs.py`
- `tests/contract/check_loop_python_sdk_contract_surface.py`
- `tests/contract/check_loop_wave_execution_policy.py`
  - keep docs/contracts aligned with the new fail-closed rule
- `docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md`
- `docs/contracts/LOOP_PYTHON_SDK_CONTRACT.md`

## Milestones
### M1. Freeze the reviewer-runtime enforcement contract
Deliverables:
- this ExecPlan
- test expectations for actual provider/runtime enforcement

Commands:
- `sed -n '1,240p' docs/agents/execplans/20260309_reviewer_profile_enforcement_loop_hardening_v0.md`

Acceptance:
- the plan is self-contained and explicitly separates execution-lane `xhigh` from reviewer-lane `low/medium`

### M2. Add TDD coverage for provider mismatch
Deliverables:
- expanded `tests/contract/check_loop_review_runner.py`
- any necessary contract-doc assertions in targeted checks

Commands:
- `uv run --locked python tests/contract/check_loop_review_runner.py`
- `uv run --locked python tests/contract/check_loop_contract_docs.py`
- `uv run --locked python tests/contract/check_loop_python_sdk_contract_surface.py`
- `uv run --locked python tests/contract/check_loop_wave_execution_policy.py`

Acceptance:
- new tests fail before implementation because runner does not yet fail closed on actual provider mismatch

### M3. Implement fail-closed reviewer enforcement and sync orchestration/docs
Deliverables:
- runtime metadata extraction in `review_canonical.py`
- profile enforcement in `review_runner.py`
- explicit reviewer-policy wiring in `review_orchestration.py`
- synced contracts/docs

Commands:
- `uv run --locked python tests/contract/check_loop_review_runner.py`
- `uv run --locked python tests/contract/check_loop_contract_docs.py`
- `uv run --locked python tests/contract/check_loop_python_sdk_contract_surface.py`
- `uv run --locked python tests/contract/check_loop_wave_execution_policy.py`

Acceptance:
- actual provider runtime metadata is persisted in canonical review artifacts
- reviewer lane mismatches return a fail-closed review result with explicit reason code/evidence
- execution lane semantics remain unchanged

### M4. Verify and close through current default reviewer policy
Deliverables:
- passing repo verification on the final byte state
- fresh maintainer AI review closeout using the committed reviewer policy (`low` baseline, `medium` bounded escalation only)

Commands:
- `uv run --locked python tests/run.py --profile core`
- `uv run --locked python tests/run.py --profile nightly`
- `lake build`
- `git diff --check`

Acceptance:
- required targeted checks pass
- `core`, `nightly`, `lake build`, and `git diff --check` pass
- final closeout carries either `AI_REVIEW_CLOSEOUT: REVIEW_RUN (...)` under low/medium policy, or explicit tooling skip evidence if the reviewer lane cannot produce a valid artifact

## Testing plan (TDD)
- Extend `tests/contract/check_loop_review_runner.py` with fixtures that emit provider banner lines showing:
  - allowed low reviewer runtime
  - allowed medium reviewer runtime
  - disallowed xhigh reviewer runtime
  - missing runtime metadata
- Assert that:
  - low/medium runtime matches succeed when the response is otherwise valid
  - xhigh runtime on reviewer lane fails closed with a distinct reason code
  - canonical attempt payloads preserve actual runtime metadata
  - orchestration helpers pass explicit reviewer policy expectations rather than trusting prompt declarations
- Keep changes deterministic by using fixture-generated stdout artifacts, not live provider calls

## Decision log
- Reviewer enforcement will trust provider-observed runtime metadata over prompt declarations.
- Execution/implementation lane capability is intentionally not narrowed by this plan; only closeout reviewer lanes are hardened.
- The fail-closed behavior should be explicit and machine-readable so later LOOP automation can route or triage mismatches without manual interpretation.

## Rollback plan
- Revert changes in:
  - `tools/loop/review_canonical.py`
  - `tools/loop/review_runner.py`
  - `tools/loop/review_orchestration.py`
  - targeted contract/doc files
- Re-run:
  - `uv run --locked python tests/contract/check_loop_review_runner.py`
  - `uv run --locked python tests/run.py --profile core`
  - `lake build`

## Outcomes & retrospective (fill when done)
- Pending implementation.
