---
title: Wave review closure hardening (mandatory post-fix re-review)
owner: codex
status: done
created: 2026-03-05
---

## Purpose / Big Picture
Wave execution already has schema/gate checks, but user feedback exposed a governance gap: a practical run can be interpreted as "one initial review + one fix, then done" without explicit closure guarantees. This plan hardens the contract and deterministic gate so review closure is explicit and enforceable. The core rule is: once a repair loop occurs, terminal closure must be produced by a later independent AI review record, not by implicit carry-over. We also add explicit anti-reuse checks for review evidence refs to prevent replaying the same review artifact as a fake re-review. This work keeps STRICT evidence auditable and prevents premature completion claims.

## Glossary
- Repair loop round: an iteration where `AI_REVIEW -> RUNNING` with `REVIEW_REPAIR_LOOP`.
- Closure review: a later AI review round that leads to terminal outcome (`PASSED|FAILED|TRIAGED`).
- Review evidence reuse: duplicated `prompt_ref` or `response_ref` across rounds that should represent distinct reviews.

## Scope
In scope:
- `docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md` (explicit closure hard rules).
- `tools/loop/wave_gate.py` (deterministic blocking checks).
- `tests/contract/check_loop_wave_blocking_gate.py` (runtime gate regression checks).
- `tests/contract/check_loop_wave_execution_policy.py` and `tests/contract/check_loop_contract_docs.py` (policy/doc hardening).
- `docs/agents/execplans/20260305_waveB_execution_loop_blocking_gate_v0.md` outcomes update.

Out of scope:
- Changing external agent providers.
- Altering Loop graph/resource contracts unrelated to Wave review closure.

## Interfaces and Files
- `validate_wave_execution_report(report, repo_root)` in `tools/loop/wave_gate.py`:
  - add review-closure checks:
    - repair-loop rounds must be followed by a later review round.
    - terminal review artifacts must not reuse prior `prompt_ref`/`response_ref`.
- Contract doc section in `LOOP_WAVE_EXECUTION_CONTRACT.md`:
  - add explicit post-fix independent re-review requirement and closure semantics.

## Milestones
1) Red tests for closure policy gaps
- Deliverables:
  - update `tests/contract/check_loop_wave_blocking_gate.py` with failing cases for:
    - missing follow-up review after repair-loop.
    - duplicated review evidence refs across rounds.
  - update `tests/contract/check_loop_contract_docs.py` required snippets.
- Commands:
  - `uv run --locked python tests/contract/check_loop_wave_blocking_gate.py`
  - `uv run --locked python tests/contract/check_loop_contract_docs.py`
- Acceptance:
  - at least one new case fails before implementation.

2) Implement deterministic closure gate + contract text
- Deliverables:
  - `tools/loop/wave_gate.py` closure checks.
  - `docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md` explicit hard-rule text.
- Commands:
  - same two targeted tests above.
- Acceptance:
  - targeted tests pass with new checks.

3) Policy-level regression and full verification
- Deliverables:
  - policy test updates in `tests/contract/check_loop_wave_execution_policy.py`.
  - update wave-B execplan outcomes with evidence references.
- Commands:
  - `uv run --locked python tests/contract/check_loop_wave_execution_policy.py`
  - `uv run --locked python tests/run.py --profile core`
  - `uv run --locked python tests/run.py --profile nightly`
- Acceptance:
  - all commands pass.

## Testing plan (TDD)
- Add deterministic negative fixtures by mutating the existing positive fixture in tests.
- Add one policy-level guard ensuring repair loops imply later closure review.
- Validate no schema drift is required unless checks exceed schema expressiveness.

## Decision log
- 2026-03-05: enforce closure as gate-level deterministic policy (not only narrative process rule), because gate checks are replayable and CI-enforceable.

## Rollback plan
- Revert edits in:
  - `tools/loop/wave_gate.py`
  - `docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md`
  - `tests/contract/check_loop_wave_blocking_gate.py`
  - `tests/contract/check_loop_wave_execution_policy.py`
  - `tests/contract/check_loop_contract_docs.py`
- Re-run:
  - `uv run --locked python tests/contract/check_loop_wave_blocking_gate.py`
  - `uv run --locked python tests/contract/check_loop_wave_execution_policy.py`

## Outcomes & retrospective (fill when done)
- Implemented hard closure checks in `tools/loop/wave_gate.py`:
  - contiguous `iteration_index` enforcement (`1..N`)
  - duplicate `prompt_ref`/`response_ref` rejection across review rounds
  - explicit `REVIEW_REPAIR_LOOP` follow-up round requirement
- Updated contract text in `docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md` with explicit closure and anti-reuse hard rules.
- Added/updated deterministic contract tests:
  - `tests/contract/check_loop_wave_blocking_gate.py`
  - `tests/contract/check_loop_wave_execution_policy.py`
  - `tests/contract/check_loop_contract_docs.py`
- Verification results:
  - `uv run --locked python tests/contract/check_loop_contract_docs.py` PASS
  - `uv run --locked python tests/contract/check_loop_wave_blocking_gate.py` PASS
  - `uv run --locked python tests/contract/check_loop_wave_execution_policy.py` PASS
  - `uv run --locked python tests/run.py --profile core` PASS
  - `uv run --locked python tests/run.py --profile nightly` PASS
  - `lake build` PASS
- Independent `codex exec` review step is recorded as `TRIAGED_TOOLING` due repeated non-terminating CLI runs in this environment; evidence:
  - `artifacts/reviews/20260305_wave_review_closure_hardening_codex_exec_review_attempts.md`
  - `artifacts/reviews/20260305_wave_review_closure_hardening_codex_exec_review.md`
