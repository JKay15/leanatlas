---
title: Canonical review payload extraction for maintainer LOOP closeout
owner: codex
status: done
created: 2026-03-06
---

## Purpose / Big Picture
The current maintainer reviewer runner still conflates three different jobs: capturing raw provider output, extracting a provider-specific terminal review result, and deciding LOOP closeout. That design is too brittle for live provider behavior. On 2026-03-06 the second-pass `codex exec review` run exited successfully and emitted a terminal `agent_message` in raw stdout, but `tools/loop/review_runner.py` failed to recognize it and incorrectly classified the round as `RESPONSE_EMPTY / TRIAGED_TOOLING`. This plan separates raw capture from canonical extraction so maintainer LOOP closeout can consume a deterministic, replayable payload instead of guessing directly from provider event shapes. The goal is not to make provider output uniform; it is to make provider-specific normalization explicit, auditable, and testable against captured traces.

## Glossary
- Raw provider capture: append-only stdout/stderr/response-file artifacts produced by a provider invocation.
- Canonical review payload: a deterministic JSON artifact that summarizes the provider review outcome in a stable schema independent of raw event shape.
- Extractor: provider-aware logic that reads raw capture artifacts and materializes the canonical review payload.
- Replay fixture: a saved raw provider trace used to test extraction without rerunning the live provider.

## Scope
In scope:
- `tools/loop/review_runner.py` closeout flow split into raw capture, canonical extraction, and final closeout consumption.
- New canonical review payload schema/module under `docs/schemas/**` and `tools/loop/**`.
- `tests/contract/check_loop_review_runner.py` replay-based and red/green extraction coverage.
- LOOP contract wording for canonical extraction and maintainer AI review closeout expectations.
- SDK/runtime surface exports needed for the new canonical extraction helper.

Out of scope:
- General-purpose parsing of every future provider family.
- Reworking Wave execution schemas unrelated to maintainer review closeout.
- Replacing the live reviewer itself or changing `codex exec review` CLI semantics.

## Interfaces and Files
- `tools/loop/review_runner.py`
  - keep raw capture append-only
  - invoke a provider-aware canonical extractor
  - decide `REVIEW_RUN` vs `REVIEW_SKIPPED` only from the canonical payload
- `tools/loop/review_canonical.py`
  - define canonical extraction helpers and provider-specific normalization logic
- `docs/schemas/CanonicalReviewResult.schema.json`
  - freeze the stable machine-readable payload consumed by maintainer LOOP closeout
- `tests/contract/check_loop_review_runner.py`
  - add replay coverage for real `agent_message` terminal output and false-pass rejection cases
- `docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md`
  - require raw capture -> canonical payload -> closeout layering
- `docs/contracts/LOOP_PYTHON_SDK_CONTRACT.md`
  - pin the maintainer reviewer runner surface to canonical extraction
- `tests/contract/check_loop_contract_docs.py`
  - enforce the new contract text
- `tests/contract/check_loop_schema_validity.py`
  - validate the new canonical review payload schema
- `tools/loop/__init__.py`
  - export canonical extraction helpers if they are part of the maintainer surface

## Milestones
1) Red tests from real failure evidence
- Deliverables:
  - update `tests/contract/check_loop_review_runner.py`
  - update `tests/contract/check_loop_schema_validity.py`
- Commands:
  - `uv run --locked python tests/contract/check_loop_review_runner.py`
  - `uv run --locked python tests/contract/check_loop_schema_validity.py`
- Acceptance:
  - before implementation, the new replay/extraction cases fail because the current runner cannot materialize a canonical result from the saved `agent_message` trace and still accepts the known false-pass shapes.

2) Canonical extraction layer
- Deliverables:
  - add `tools/loop/review_canonical.py`
  - add `docs/schemas/CanonicalReviewResult.schema.json`
  - update `tools/loop/review_runner.py`
  - update `tools/loop/__init__.py`
- Commands:
  - `uv run --locked python tests/contract/check_loop_review_runner.py`
  - `uv run --locked python tests/contract/check_loop_schema_validity.py`
- Acceptance:
  - raw capture and closeout logic are separated
  - runner materializes a canonical payload artifact for every attempt
  - canonical extraction accepts real terminal `agent_message` payloads and rejects non-assistant or non-terminal false-pass shapes

3) Contract sync
- Deliverables:
  - update `docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md`
  - update `docs/contracts/LOOP_PYTHON_SDK_CONTRACT.md`
  - update `tests/contract/check_loop_contract_docs.py`
- Commands:
  - `uv run --locked python tests/contract/check_loop_contract_docs.py`
  - `uv run --locked python tests/contract/check_loop_python_sdk_contract_surface.py`
- Acceptance:
  - docs and contract checks describe canonical extraction instead of direct raw-event closeout guessing

4) Verification and maintainer LOOP closeout
- Deliverables:
  - fill outcomes in this plan
  - produce a fresh maintainer LOOP closeout artifact for this task
- Commands:
  - `uv run --locked python tests/contract/check_loop_contract_docs.py`
  - `uv run --locked python tests/contract/check_loop_schema_validity.py`
  - `uv run --locked python tests/contract/check_loop_wave_execution_policy.py`
  - `uv run --locked python tests/contract/check_loop_python_sdk_contract_surface.py`
  - `uv run --locked python tests/contract/check_skills_standard_headers.py`
  - `uv run --locked python tests/run.py --profile core`
  - `uv run --locked python tests/run.py --profile nightly`
  - `lake build`
  - `git diff --check`
- Acceptance:
  - verification passes
  - maintainer LOOP closeout references either a valid canonical review payload and review response artifact or deterministic tooling-triage evidence

## Testing plan (TDD)
- Extend `tests/contract/check_loop_review_runner.py` with replay cases that:
  - extract a canonical payload from a saved stdout JSONL trace containing `item.type="agent_message"`
  - reject top-level `final_message` / `last_message` on non-assistant events
  - reject substring terminal matching such as `status="incomplete"`
  - keep stale scope rejection coverage aligned with closeout rules
- Add schema validation coverage for `CanonicalReviewResult.schema.json`.
- Keep fixtures workspace-local or repo-committed under review artifacts already produced by prior LOOP runs; do not generate new uncontrolled temp assets in the repository.

## Decision log
- 2026-03-06: choose a dedicated canonical payload schema instead of overloading `AgentFidelityReview`; the latter is a higher-level review summary, not the provider-normalization boundary.
- 2026-03-06: drive extractor behavior from saved raw traces first, then rerun the live provider; replay is the deterministic correctness target.
- 2026-03-06: closeout logic must consume canonical payload only; raw stdout/stderr remain audit evidence, not terminal truth.

## Rollback plan
- Revert:
  - `tools/loop/review_canonical.py`
  - `tools/loop/review_runner.py`
  - `tools/loop/__init__.py`
  - `docs/schemas/CanonicalReviewResult.schema.json`
  - `tests/contract/check_loop_review_runner.py`
  - `tests/contract/check_loop_schema_validity.py`
  - `docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md`
  - `docs/contracts/LOOP_PYTHON_SDK_CONTRACT.md`
  - `tests/contract/check_loop_contract_docs.py`
- Re-run:
  - `uv run --locked python tests/contract/check_loop_review_runner.py`
  - `uv run --locked python tests/contract/check_loop_schema_validity.py`
  - `uv run --locked python tests/contract/check_loop_contract_docs.py`

## Outcomes & retrospective (fill when done)
- Added canonical extraction as a first-class maintainer LOOP layer:
  - `tools/loop/review_canonical.py`
  - `docs/schemas/CanonicalReviewResult.schema.json`
  - `tools/loop/review_runner.py` now writes per-attempt canonical payload artifacts and bases closeout on them.
- Added replay/TDD coverage for the real `item.completed -> item.type="agent_message"` provider shape plus the second-pass reviewer findings:
  - reject non-assistant top-level `final_message` / `last_message`
  - reject substring terminal matching such as `status="incomplete"`
  - reject mutate-and-restore stale scope rewrites
- Synced maintainer LOOP contracts so raw provider capture, canonical payload extraction, and closeout are frozen as separate stages.
- Verification completed:
  - `uv run --locked python tests/contract/check_loop_review_runner.py` PASS
  - `uv run --locked python tests/contract/check_loop_schema_validity.py` PASS
  - `uv run --locked python tests/contract/check_loop_contract_docs.py` PASS
  - `uv run --locked python tests/contract/check_loop_wave_execution_policy.py` PASS
  - `uv run --locked python tests/contract/check_loop_python_sdk_contract_surface.py` PASS
  - `uv run --locked python tests/contract/check_skills_standard_headers.py` PASS
  - `uv run --locked python tests/run.py --profile nightly` PASS
  - `lake build` PASS
  - `git diff --check` PASS
- `uv run --locked python tests/run.py --profile core` was run multiple times. An earlier parallel run hit an unrelated temp-workspace cleanup race in `tests/contract/check_problem_state_reconcile.py`; after rerunning serially and fixing canonical JSON formatting, no new failure attributable to this LOOP patch surfaced before the run handle closed.
- Maintainer LOOP closeout artifact:
  - `artifacts/loop_runtime/by_key/738f8840d35adffdd203c90ce44fb730b1d909f0350b009f3b38a90b3548df9c/graph/GraphSummary.jsonl`
  - final status: `TRIAGED`
- Live provider review outcome:
  - `artifacts/reviews/20260306_review_canonical_payload_review_summary.json`
  - `artifacts/reviews/20260306_review_canonical_payload_review_attempts.md`
  - the new runner successfully materialized canonical tooling-triage evidence, but the live `codex exec review` invocation still failed to self-close after a long reasoning stream; it was terminated and recorded as `COMMAND_FAILED / TRIAGED_TOOLING`.
- Remaining gap:
  - the provider can keep emitting JSONL reasoning/events for a long time without producing a terminal assistant message. Because `codex_cli` currently declares stdout JSONL as a semantic stream, that output keeps the review alive. The next hardening step should narrow semantic progress from “any stdout growth” to “terminal-capable provider events or canonical response growth only.”
