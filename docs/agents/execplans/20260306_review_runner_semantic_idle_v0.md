---
title: Reviewer runner semantic-idle hardening for maintainer LOOP closeout
owner: codex
status: active
created: 2026-03-06
---

## Purpose / Big Picture
The current maintainer reviewer runner can reject empty responses and missing terminal events only after the provider process exits. That leaves a tooling gap: a provider may keep emitting stderr warnings or heartbeat noise forever while never producing a canonical response or terminal assistant event. In that state transport-level idle never triggers, so the AI review node cannot close deterministically without human intervention. This plan adds a semantic-idle gate to the reviewer runner so maintainer LOOP closeout can distinguish "process still noisy" from "review still making semantic progress". The goal is not to make provider behavior perfect; it is to make maintainer LOOP closeout deterministic even when provider closeout semantics are weak.

## Glossary
- Semantic progress: reviewer-visible progress that can legitimately lead to a canonical closeout artifact, limited to response-file growth, provider-event stream growth, or canonical extracted response updates.
- Semantic idle timeout: bounded wall-clock window during which no semantic progress occurs, even if transport output continues.
- Provider event stream: structured provider output, currently the stdout JSONL stream used by the `codex_cli` adapter.
- Canonical response: the non-empty `response_ref` artifact accepted by LOOP as the review result.

## Scope
In scope:
- `tools/loop/review_runner.py` semantic-idle execution and attempt classification.
- `tests/contract/check_loop_review_runner.py` red/green coverage for semantic-idle behavior.
- LOOP contract text that defines semantic-idle expectations for maintainer AI review nodes.

Out of scope:
- General changes to `tools/workflow/run_cmd.py`.
- New provider families beyond the current `codex_cli` and generic response-file adapters.
- Changes to LOOP graph schema or maintainer graph topology.

## Interfaces and Files
- `tools/loop/review_runner.py`
  - Add a semantic-idle-aware execution path for provider review commands.
  - Preserve append-only attempt artifacts and existing closeout surface.
  - Extend summary/attempt evidence with semantic-idle reasoning.
- `tests/contract/check_loop_review_runner.py`
  - Add regression coverage for stderr churn with no semantic progress.
  - Keep existing success, stale-input, timeout, and terminal-event behaviors intact.
- `docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md`
  - Freeze semantic-idle expectations for provider-invoked reviewer nodes.
- `docs/contracts/LOOP_PYTHON_SDK_CONTRACT.md`
  - Freeze SDK-facing maintainer runner expectation that transport idle and semantic idle are distinct gates.
- `tests/contract/check_loop_contract_docs.py`
  - Enforce the new contract wording.

## Milestones
1) Red test for semantic-idle triage
- Deliverables:
  - update `tests/contract/check_loop_review_runner.py`
- Commands:
  - `uv run --locked python tests/contract/check_loop_review_runner.py`
- Acceptance:
  - before implementation, the new semantic-idle scenario fails because stderr churn still keeps the provider alive until transport timeout or manual intervention.

2) Implement semantic-idle-aware reviewer execution
- Deliverables:
  - update `tools/loop/review_runner.py`
- Commands:
  - `uv run --locked python tests/contract/check_loop_review_runner.py`
- Acceptance:
  - semantic-idle scenario passes without regressing existing success/timeout/terminal-event cases.

3) Contract sync
- Deliverables:
  - update `docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md`
  - update `docs/contracts/LOOP_PYTHON_SDK_CONTRACT.md`
  - update `tests/contract/check_loop_contract_docs.py`
- Commands:
  - `uv run --locked python tests/contract/check_loop_contract_docs.py`
- Acceptance:
  - contract doc check passes and wording matches implemented behavior.

4) Verification + maintainer LOOP closeout
- Deliverables:
  - fill outcomes in this plan
  - produce a fresh maintainer LOOP closeout artifact for this task
- Commands:
  - `uv run --locked python tests/run.py --profile core`
  - `uv run --locked python tests/run.py --profile nightly`
  - `lake build`
  - `git diff --check`
- Acceptance:
  - verification passes
  - final closeout references either a valid reviewer response artifact or deterministic tooling-triage evidence from the semantic-idle gate

## Testing plan (TDD)
- Extend `tests/contract/check_loop_review_runner.py` with a helper mode that emits periodic stderr warnings while never producing a response artifact or terminal JSON event.
- Require the runner to triage this case as tooling failure within a short semantic-idle window even when transport output continues.
- Re-run existing cases for:
  - success via response file
  - success via terminal JSON event
  - stale input rejection
  - retry after non-zero exit
  - transport timeout
- Keep all test-only artifacts inside temporary workspaces.

## Decision log
- 2026-03-06: implement semantic-idle monitoring inside `tools/loop/review_runner.py` rather than widening `run_cmd`; the reviewer runner needs provider-aware semantic progress detection that the generic command runner should not own.
- 2026-03-06: keep the public runner surface narrow; add an optional `semantic_idle_timeout_s` rather than introducing a new public API family.
- 2026-03-06: amended during implementation after `contract_tools_subprocess_wrapper` failed. Semantic-idle monitoring was moved into `tools/workflow/run_cmd.py` so `tools/**` still obeys the wrapper-only subprocess policy.

## Rollback plan
- Revert:
  - `tools/loop/review_runner.py`
  - `tests/contract/check_loop_review_runner.py`
  - `docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md`
  - `docs/contracts/LOOP_PYTHON_SDK_CONTRACT.md`
  - `tests/contract/check_loop_contract_docs.py`
- Re-run:
  - `uv run --locked python tests/contract/check_loop_review_runner.py`
  - `uv run --locked python tests/contract/check_loop_contract_docs.py`

## Outcomes & retrospective (fill when done)
- Added semantic-idle support to `tools/workflow/run_cmd.py` with:
  - `semantic_idle_timeout_s`
  - `semantic_activity_streams`
  - `semantic_activity_paths`
  - `timeout_kind="semantic"` evidence in the command span
- Updated `tools/loop/review_runner.py` to:
  - route semantic-idle monitoring through `run_cmd`
  - reject stale scope mutations before accepting a non-empty response
  - restrict JSON fallback synthesis to terminal assistant messages only
- Extended `tests/contract/check_loop_review_runner.py` with regression coverage for:
  - stale scope mutation during execution
  - non-assistant terminal-looking JSON events
  - semantic-idle progress when transport idle is disabled
  - stderr-only semantic-idle triage
- Synced maintainer LOOP contract wording in:
  - `docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md`
  - `docs/contracts/LOOP_PYTHON_SDK_CONTRACT.md`
  - `tests/contract/check_loop_contract_docs.py`
- Verification:
  - `uv run --locked python tests/contract/check_loop_review_runner.py` PASS
  - `uv run --locked python tests/contract/check_loop_contract_docs.py` PASS
  - `uv run --locked python tests/contract/check_run_cmd_timeout_hardening.py` PASS
  - `uv run --locked python tests/contract/check_tools_subprocess_wrapper.py` PASS
  - `uv run --locked python tests/run.py --profile core` PASS
  - `uv run --locked python tests/run.py --profile nightly` PASS (`agent-eval-real` entries `SKIP` by design because `LEANATLAS_REAL_AGENT_CMD` / `LEANATLAS_REAL_AGENT_PROVIDER` are unset)
  - `lake build` PASS
  - `git diff --check` PASS
- AI review results:
  - first reviewer pass produced a valid `REVIEW_RUN` and found 3 correctness issues, all fixed in this task:
    - `artifacts/reviews/20260306_review_runner_semantic_idle_review_summary.json`
    - `artifacts/reviews/20260306_review_runner_semantic_idle_review_response.md`
  - second reviewer pass on the fixes ended as tooling triage because the provider exited without a usable final message (`RESPONSE_EMPTY`):
    - `artifacts/reviews/20260306_review_runner_semantic_idle_review_round2_summary.json`
    - `artifacts/reviews/20260306_review_runner_semantic_idle_review_round2_attempts.md`
