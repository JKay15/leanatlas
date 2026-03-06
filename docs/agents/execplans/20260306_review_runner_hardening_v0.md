---
title: Maintainer reviewer-runner hardening for LOOP closeout
owner: codex
status: done
created: 2026-03-06
---

## Purpose / Big Picture
Maintainer LOOP closeout currently depends on ad-hoc `codex exec review` shell usage. That leaves a gap between contract text and executable behavior: reviewer runs can timeout, return non-zero, or never materialize the expected response artifact, and the maintainer closeout path has no single deterministic runner that records those outcomes. This plan introduces a reusable reviewer runner for LOOP so maintainer AI review nodes can execute with bounded behavior, append-only attempt evidence, and deterministic tooling-triage classification. The immediate goal is to stop treating reviewer invocation as an informal shell step and instead make it a first-class, auditable runtime primitive. The completion condition for this task is stronger than "tests pass": this task's own AI review closeout must be executed through the hardened runner.

## Glossary
- Reviewer runner: a deterministic helper that launches provider review commands, enforces timeouts and scope requirements, and records attempt artifacts.
- Review scope: the exact repo files or paths that the reviewer is allowed to inspect for one closeout attempt.
- Stale diff: a review attempt whose input fingerprint no longer matches the current content of the requested scope files.
- Attempt log: append-only record of reviewer invocations, including command evidence and tooling-triage reasons.

## Scope
In scope:
- `tools/loop/**` additions/updates needed to run bounded maintainer AI reviews with deterministic artifacts.
- Contract/doc updates for reviewer-runner requirements in LOOP maintainer paths.
- New contract tests for reviewer-runner policy and maintainer integration.
- Test registry/matrix updates caused by the new tests.

Out of scope:
- Changing LOOP graph schema shape.
- Replacing `tools/workflow/run_cmd.py` timeout semantics.
- Generalizing provider support beyond the existing `codex exec review` contract surface.

## Interfaces and Files
- `tools/loop/review_runner.py` (new)
  - Provide a deterministic runner for provider review commands.
  - Enforce non-empty scoped file list, bounded execution, response-file existence/non-empty checks, and stale-input detection.
  - Persist append-only attempt evidence under `artifacts/reviews/`.
- `tools/loop/maintainer.py`
  - Expose the review-runner output in a form maintainer closeout can consume.
- `tools/loop/__init__.py`
  - Export the new runner surface lazily.
- `tests/contract/check_loop_review_runner.py` (new)
  - Cover policy and artifact guarantees for success, stale input, timeout/non-zero, and missing response evidence.
- `tests/contract/check_loop_contract_docs.py`
  - Enforce reviewer-runner contract wording.
- `docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md`
- `docs/contracts/LOOP_PYTHON_SDK_CONTRACT.md`
- `tests/manifest.json`
- `docs/testing/TEST_MATRIX.md`

## Milestones
1) Red tests for reviewer-runner policy
- Deliverables:
  - new `tests/contract/check_loop_review_runner.py`
  - doc-snippet expectations updated in `tests/contract/check_loop_contract_docs.py`
- Commands:
  - `uv run --locked python tests/contract/check_loop_review_runner.py`
  - `uv run --locked python tests/contract/check_loop_contract_docs.py`
- Acceptance:
  - new test fails before implementation because runner surface/behavior is missing.

2) Implement deterministic reviewer runner
- Deliverables:
  - `tools/loop/review_runner.py`
  - minimal maintainer integration/export updates
- Commands:
  - `uv run --locked python tests/contract/check_loop_review_runner.py`
- Acceptance:
  - targeted reviewer-runner test passes for success and tooling-triage paths.

3) Contract + registry sync
- Deliverables:
  - LOOP contract updates for file scope, response evidence, stale diff handling, and tooling-triage attempts
  - `tests/manifest.json` / `docs/testing/TEST_MATRIX.md` updated
- Commands:
  - `uv run --locked python tests/contract/check_loop_contract_docs.py`
  - `uv run --locked python tests/contract/check_test_registry.py`
- Acceptance:
  - contract doc check passes and registry remains consistent.

4) Full verification + self-hosted closeout
- Deliverables:
  - verification notes in this plan outcome section
  - this task's own AI review closeout executed through the hardened runner
- Commands:
  - `uv run --locked python tests/run.py --profile core`
  - `uv run --locked python tests/run.py --profile nightly`
  - `lake build`
- Acceptance:
  - verification commands pass
  - final closeout references a runner-produced review artifact or deterministic tooling-triage artifact

## Testing plan (TDD)
- Add a dedicated contract test that creates a temporary workspace and fake reviewer scripts to exercise:
  - missing review scope rejection
  - stale input fingerprint rejection before invocation
  - missing/empty response file after apparently successful command
  - bounded timeout/non-zero exit evidence persisted to attempts log
  - successful invocation with non-empty response artifact
- Reuse `run_cmd` so subprocess evidence remains within the existing workflow contract.

## Decision log
- 2026-03-06: keep reviewer-runner provider surface narrow and deterministic for now; avoid premature provider abstraction until the maintainer closeout path is stable.
- 2026-03-06: local `codex exec review` CLI on this machine accepts prompt text positionally with `-o/--output-last-message`; it does not accept the older `--reviewer/--prompt-file/--out` shape. Keep LOOP semantics provider-neutral, but update the non-normative contract example to the locally valid invocation form.

## Rollback plan
- Revert changes to:
  - `tools/loop/review_runner.py`
  - `tools/loop/maintainer.py`
  - `tools/loop/__init__.py`
  - updated contracts/tests/manifest/matrix
- Re-run:
  - `uv run --locked python tests/contract/check_loop_review_runner.py`
  - `uv run --locked python tests/contract/check_loop_contract_docs.py`

## Outcomes & retrospective (fill when done)
- Added `tools/loop/review_runner.py` with:
  - `compute_review_scope_fingerprint(...)`
  - `run_review_closure(...)`
  - enforced non-empty file scope, stale-input rejection, bounded subprocess execution via `run_cmd`, response existence/non-empty gate, and append-only attempt evidence under `artifacts/reviews/`.
- Exported the runner from `tools/loop/__init__.py` and extended package-import regression coverage so the new surface stays jsonschema-optional at import time.
- Added contract coverage in `tests/contract/check_loop_review_runner.py` for:
  - empty scope rejection
  - successful review closure
  - stale fingerprint rejection
  - retry after command failure
  - missing response artifact
  - timeout evidence
- Synced contracts/registry/docs:
  - `docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md`
  - `docs/contracts/LOOP_PYTHON_SDK_CONTRACT.md`
  - `tests/contract/check_loop_contract_docs.py`
  - `tests/manifest.json`
  - `docs/testing/TEST_MATRIX.md`
  - `docs/setup/TEST_ENV_INVENTORY.md`
- Verification:
  - `uv run --locked python tests/contract/check_loop_review_runner.py` PASS
  - `uv run --locked python tests/contract/check_loop_contract_docs.py` PASS
  - `uv run --locked python tests/contract/check_loop_schema_validity.py` PASS
  - `uv run --locked python tests/contract/check_loop_wave_execution_policy.py` PASS
  - `uv run --locked python tests/contract/check_loop_python_sdk_contract_surface.py` PASS
  - `uv run --locked python tests/contract/check_skills_standard_headers.py` PASS
  - `uv run --locked python tests/run.py --profile core` PASS
  - `uv run --locked python tests/run.py --profile nightly` PASS (`agent-eval-real` paths SKIP as designed because `LEANATLAS_REAL_AGENT_CMD` / `LEANATLAS_REAL_AGENT_PROVIDER` are unset)
  - `lake build` PASS
  - `git diff --check` PASS
- Self-hosted closeout outcome:
  - first runner-driven review attempt completed deterministically as tooling triage because the older CLI example shape was invalid on this machine; summary artifact:
    - `artifacts/reviews/20260306_review_runner_hardening_review_summary.json`
  - after correcting the non-normative contract example to the local CLI form, a later provider attempt was allowed to run to its own terminal state. It exited after 6 minutes 27 seconds with `exit_code=0`, but the response file remained empty, so the runner classified it as `RESPONSE_EMPTY / TRIAGED_TOOLING` rather than accepting a false pass:
    - `artifacts/reviews/20260306_review_runner_hardening_review_retry2_summary.json`
