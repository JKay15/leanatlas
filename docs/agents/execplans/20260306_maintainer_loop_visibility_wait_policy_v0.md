---
title: Upfront maintainer LOOP materialization and review wait-policy hardening
owner: codex
status: active
created: 2026-03-06
---

## Purpose / Big Picture
The current maintainer LOOP support proves that a maintainer graph can be recorded, but it is still too easy to do work first and only write graph evidence at closeout time. That weakens the core claim that non-trivial maintainer work is actually being executed through LOOP rather than merely annotated after the fact. Separately, maintainer AI review waiting policy is not yet explicit enough: recent runs were closed too aggressively based on operator judgment even though `codex exec review` can spend a long time in high-thinking modes before emitting a terminal answer. This plan hardens both edges. First, maintainer work must materialize a canonical LOOP run bundle before implementation begins and append node-journal evidence as work progresses. Second, review waiting policy must explicitly forbid subjective early termination and require provider-aware minimum observation windows plus deterministic timeout semantics.

## Glossary
- Maintainer session: the upfront artifact bundle that freezes a maintainer change’s `graph_spec`, run key, and initial node journal before implementation starts.
- Node journal: append-only per-node status evidence showing what has already been completed in the maintainer LOOP sequence.
- Observation window: the minimum provider-runtime interval before a reviewer attempt may be considered stalled or tooling-triaged.
- Transport idle: no stdout/stderr growth.
- Semantic idle: no provider progress toward a terminal review result.

## Scope
In scope:
- `tools/loop/maintainer.py` upfront session/materialization helpers and append-only node journal artifacts.
- `tools/loop/review_runner.py` defaults / policy enforcement for review waiting.
- LOOP contracts/docs/tests describing visible maintainer graph execution and review waiting semantics.
- TDD coverage for the new maintainer session artifacts and policy text.

Out of scope:
- Reworking the general graph runtime scheduler.
- Changing `codex exec review` CLI behavior.
- Converting every historical artifact to the new session format.

## Interfaces and Files
- `tools/loop/maintainer.py`
  - add helpers to materialize a maintainer run before implementation begins
  - persist append-only session and node-journal artifacts
- `tools/loop/__init__.py`
  - export the new maintainer session helpers
- `tools/loop/review_runner.py`
  - encode provider-aware minimum observation policy for maintainer review attempts
- `docs/contracts/LOOP_GRAPH_CONTRACT.md`
  - require upfront maintainer graph/session materialization and node-journal visibility
- `docs/contracts/LOOP_PYTHON_SDK_CONTRACT.md`
  - pin maintainer orchestration to Python helper materialization rather than post-hoc summaries only
- `docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md`
  - define review waiting policy, including prohibition on subjective early termination
- `tests/contract/check_maintainer_loop_requirement.py`
  - enforce the new maintainer session / visibility wording
- `tests/contract/check_loop_review_runner.py`
  - cover provider minimum observation semantics
- `tests/contract/check_loop_contract_docs.py`
  - require the new contract snippets

## Milestones
1) Red tests and contract assertions
- Deliverables:
  - update `tests/contract/check_maintainer_loop_requirement.py`
  - update `tests/contract/check_loop_review_runner.py`
  - update `tests/contract/check_loop_contract_docs.py`
- Commands:
  - `uv run --locked python tests/contract/check_maintainer_loop_requirement.py`
  - `uv run --locked python tests/contract/check_loop_review_runner.py`
  - `uv run --locked python tests/contract/check_loop_contract_docs.py`
- Acceptance:
  - tests fail before implementation because the repo does not yet require upfront maintainer session materialization or explicit non-subjective review waiting rules.

2) Upfront maintainer session layer
- Deliverables:
  - update `tools/loop/maintainer.py`
  - update `tools/loop/__init__.py`
- Commands:
  - `uv run --locked python tests/contract/check_maintainer_loop_requirement.py`
- Acceptance:
  - Python helpers can materialize a maintainer session before implementation starts
  - session artifacts include canonical `graph_spec`, run key, and append-only node journal entries
  - closeout helpers remain compatible with the canonical graph summary flow

3) Review wait-policy hardening
- Deliverables:
  - update `tools/loop/review_runner.py`
  - update `docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md`
  - update `docs/contracts/LOOP_PYTHON_SDK_CONTRACT.md`
  - update `docs/contracts/LOOP_GRAPH_CONTRACT.md`
- Commands:
  - `uv run --locked python tests/contract/check_loop_review_runner.py`
  - `uv run --locked python tests/contract/check_loop_contract_docs.py`
- Acceptance:
  - maintainer review waiting policy is explicit and provider-aware
  - subjective “too slow” closeout is forbidden
  - default observation windows are documented and enforced for `codex_cli`

4) Verification and LOOP closeout
- Deliverables:
  - fill outcomes in this plan
  - produce a maintainer LOOP closeout artifact for this task
- Commands:
  - `uv run --locked python tests/contract/check_maintainer_loop_requirement.py`
  - `uv run --locked python tests/contract/check_loop_review_runner.py`
  - `uv run --locked python tests/contract/check_loop_contract_docs.py`
  - `uv run --locked python tests/contract/check_loop_schema_validity.py`
  - `uv run --locked python tests/contract/check_loop_wave_execution_policy.py`
  - `uv run --locked python tests/contract/check_loop_python_sdk_contract_surface.py`
  - `uv run --locked python tests/run.py --profile core`
  - `uv run --locked python tests/run.py --profile nightly`
  - `lake build`
  - `git diff --check`
- Acceptance:
  - targeted checks pass
  - full verification is documented
  - maintainer LOOP evidence shows the task’s graph was materialized before closeout

## Testing plan (TDD)
- Extend `tests/contract/check_maintainer_loop_requirement.py` to require upfront maintainer session materialization and node-journal visibility in contracts.
- Extend `tests/contract/check_loop_review_runner.py` with policy-focused cases or assertions covering provider minimum observation defaults / early-termination prohibition.
- Extend `tests/contract/check_loop_contract_docs.py` with the new required snippets.
- Keep fixtures deterministic and repo-local; no new ad-hoc artifacts under tracked dirs beyond committed fixtures/tests.

## Decision log
- 2026-03-06: treat “I used LOOP” as an artifact visibility problem, not merely a prose problem. The fix is a session layer, not a stronger paragraph in the final answer.
- 2026-03-06: provider waiting policy must be written into contracts and defaults; relying on operator judgment is incompatible with auditable closeout.

## Rollback plan
- Revert:
  - `tools/loop/maintainer.py`
  - `tools/loop/__init__.py`
  - `tools/loop/review_runner.py`
  - `docs/contracts/LOOP_GRAPH_CONTRACT.md`
  - `docs/contracts/LOOP_PYTHON_SDK_CONTRACT.md`
  - `docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md`
  - `tests/contract/check_maintainer_loop_requirement.py`
  - `tests/contract/check_loop_review_runner.py`
  - `tests/contract/check_loop_contract_docs.py`
- Re-run the targeted checks listed above to confirm rollback.

## Outcomes & retrospective (fill when done)
- Pending.
