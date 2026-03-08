---
title: Implement exhaustive reviewer prompt engineering and controlled prompt protocol experiments
owner: Codex (local workspace)
status: done
created: 2026-03-08
parent_execplan: docs/agents/execplans/20260307_loop_core_parallel_nested_batch_v0.md
---

## Purpose / Big Picture
The current LOOP reviewer path compiles tiered review plans and executes deterministic closeout, but it does not yet enforce an explicit "exhaustive reviewer" protocol. In practice that means reviewers often emit only a small subset of actionable findings per round, especially on expensive `medium`/`xhigh` runs, and the system pays for multiple rounds of partial discovery. This wave fixes that at the protocol layer rather than by changing model tiers again.

The target outcome is a canonical prompt/protocol surface that tells provider-invoked reviewers to scan broadly, search multiple risk categories, dedupe findings, and only finalize after an omission self-check. The implementation must also support a controlled-variable experiment artifact so future evaluations can compare baseline and exhaustive prompt variants under the same scope/context/provider settings. The result should be a mainline LOOP reviewer path that encourages one-pass high-recall review and makes "anti-dribble" behavior auditable instead of accidental.

## Glossary
- exhaustive reviewer protocol: a canonical prompt contract that requires broad coverage, category-based scanning, omission self-checks, and one-pass batched findings.
- anti-dribble: policy that reviewers should not stop after the first few findings when more findings are plausibly discoverable in the same frozen scope.
- controlled prompt experiment: a deterministic artifact pair where baseline and exhaustive prompt variants share the same scope/context/provider metadata and differ only in prompt protocol.
- prompt protocol id: a stable identifier for the prompt semantics expected by runners/bundles/docs.

## Scope
In scope:
- add a canonical review-prompting helper under `tools/loop/**`
- expose an explicit exhaustive prompt protocol and a baseline protocol for controlled experiments
- wire prompt protocol metadata into review strategy/orchestration sidecars
- let reviewer runners optionally require a canonical prompt protocol before launch
- update LOOP contracts/docs/tests to describe exhaustive reviewer expectations
- materialize deterministic controlled-variable prompt experiments for future reviewer studies

Out of scope:
- changing global reviewer tier defaults again
- implementing batch supervisor/autopilot
- repairing existing fresh-`xhigh` findings from unrelated waves
- forcing every existing historical prompt artifact to be rewritten retroactively

Allowed directories:
- `tools/loop/**`
- `docs/contracts/**`
- `docs/agents/execplans/**`
- `tests/contract/**`
- `docs/testing/**`
- `docs/navigation/**`

Forbidden:
- `.cache/leanatlas/tmp/**` as primary implementation location
- unrelated formalization or repair-wave code

## Interfaces and Files
Primary implementation files:
- `tools/loop/review_strategy.py`
- `tools/loop/review_orchestration.py`
- `tools/loop/review_runner.py`
- new helper module under `tools/loop/` for prompt protocol generation/validation
- `tools/loop/__init__.py`
- `docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md`
- `docs/contracts/LOOP_PYTHON_SDK_CONTRACT.md`

Primary tests:
- `tests/contract/check_loop_review_strategy.py`
- `tests/contract/check_loop_review_orchestration.py`
- `tests/contract/check_loop_review_runner.py`
- new contract test for prompt protocol / controlled prompt experiments

Registry/index files if new test module is added:
- `tests/manifest.json`
- `docs/testing/TEST_MATRIX.md`
- `docs/navigation/FILE_INDEX.md`

## Milestones
### 1) Freeze exhaustive prompt protocol acceptance in tests
Deliverables:
- add/update tests that fail until the mainline exports a canonical exhaustive reviewer protocol
- add deterministic checks for a controlled prompt experiment pair where only protocol text/ids differ
- add runner-side checks for optional prompt protocol enforcement

Commands:
- `uv run --locked python tests/contract/check_loop_review_strategy.py`
- `uv run --locked python tests/contract/check_loop_review_orchestration.py`
- `uv run --locked python tests/contract/check_loop_review_runner.py`

Acceptance:
- tests fail before implementation
- controlled prompt experiment proves same scope/context/provider metadata across baseline vs exhaustive variants

### 2) Implement canonical review prompt/protocol helpers
Deliverables:
- canonical baseline and exhaustive protocol ids
- deterministic prompt renderer for exhaustive reviewer mode
- prompt parser/validator for runner-side enforcement
- controlled prompt experiment helper

Commands:
- `uv run --locked python tests/contract/check_loop_review_strategy.py`

Acceptance:
- exhaustive prompt contains explicit coverage axes, anti-dribble instructions, and omission self-check requirements
- controlled prompt experiment artifacts are stable and replayable

### 3) Wire prompt protocol metadata into orchestration and runner surfaces
Deliverables:
- review strategy/orchestration sidecars expose prompt protocol metadata
- reviewer runner can require a canonical exhaustive protocol before provider launch
- SDK/exports surface exposes the new helper(s)

Commands:
- `uv run --locked python tests/contract/check_loop_review_orchestration.py`
- `uv run --locked python tests/contract/check_loop_review_runner.py`

Acceptance:
- orchestration metadata makes the intended prompt protocol visible to later executors/auditors
- runner refuses malformed/exhaustiveness-incomplete prompts when exhaustive protocol is required

### 4) Align contracts/docs with anti-dribble policy
Deliverables:
- LOOP contracts describe the exhaustive reviewer protocol, anti-dribble rule, and controlled prompt experiment semantics

Commands:
- `uv run --locked python tests/contract/check_loop_contract_docs.py`
- `uv run --locked python tests/contract/check_loop_python_sdk_contract_surface.py`

Acceptance:
- docs/contracts no longer imply that "report actionable findings" alone is enough for high-recall review

### 5) Verify and close
Deliverables:
- full targeted verification
- maintainer LOOP closeout with non-`xhigh` routine review; `xhigh` only if explicitly used to test the new protocol effect

Commands:
- `uv run --locked python tests/contract/check_loop_contract_docs.py`
- `uv run --locked python tests/contract/check_loop_schema_validity.py`
- `uv run --locked python tests/contract/check_loop_wave_execution_policy.py`
- `uv run --locked python tests/contract/check_loop_python_sdk_contract_surface.py`
- `uv run --locked python tests/contract/check_loop_review_strategy.py`
- `uv run --locked python tests/contract/check_loop_review_orchestration.py`
- `uv run --locked python tests/contract/check_loop_review_runner.py`
- `uv run --locked python tests/run.py --profile core`
- `lake build`

Acceptance:
- new prompt/protocol helpers are in mainline
- controlled prompt experiment support exists
- routine closeout does not require `xhigh`

## Testing plan (TDD)
- Update/add prompt-protocol tests first
- Only then implement helper module and runner/orchestration wiring
- Rerun:
  - `tests/contract/check_loop_review_strategy.py`
  - `tests/contract/check_loop_review_orchestration.py`
  - `tests/contract/check_loop_review_runner.py`
  - `tests/contract/check_loop_contract_docs.py`
  - `tests/contract/check_loop_python_sdk_contract_surface.py`
  - `tests/contract/check_loop_wave_execution_policy.py`
  - `tests/run.py --profile core`
  - `lake build`

## Decision log
- 2026-03-08: treat reviewer exhaustiveness/anti-dribble as a protocol-layer problem, not a pure model-tier problem.
- 2026-03-08: require controlled-variable prompt experiments so future reviewer comparisons can isolate prompt protocol from scope/context/provider drift.
- 2026-03-08: keep routine closeout off `xhigh`; only use `xhigh` if explicitly testing whether the exhaustive protocol improves high-tier one-pass recall.

## Rollback plan
- revert the new prompt helper module plus runner/orchestration/docs/tests
- verify rollback with:
  - `uv run --locked python tests/contract/check_loop_review_strategy.py`
  - `uv run --locked python tests/contract/check_loop_review_orchestration.py`
  - `uv run --locked python tests/run.py --profile core`

## Outcomes & retrospective (fill when done)
- Implemented:
  - Added `tools/loop/review_prompting.py` with canonical baseline/exhaustive prompt protocols, deterministic inspection helpers, and controlled prompt experiment generation.
  - Wired prompt protocol metadata into review strategy/orchestration/runtime surfaces and enforced exhaustive protocol preservation for authoritative replay bundles.
  - Hardened `run_review_closure(...)` so canonical prompts must match frozen run inputs exactly, canonical validation normalizes CRLF/LF differences, and non-canonical prompts no longer claim canonical `prompt_protocol_id` in persisted context packs.
  - Added contract tests covering canonical prompt parsing, CRLF tolerance, controlled prompt experiments, replay downgrade rejection, and context-pack protocol provenance.
- Verification:
  - Targeted contract checks passed:
    - `check_loop_review_prompting.py`
    - `check_loop_review_runner.py`
    - `check_loop_review_strategy.py`
    - `check_loop_review_orchestration.py`
    - `check_loop_contract_docs.py`
    - `check_loop_python_sdk_contract_surface.py`
    - `check_file_index_reachability.py`
  - Full sequential verification passed:
    - `tests/run.py --profile core`
    - `tests/run.py --profile nightly`
    - `lake build`
    - `git diff --check`
  - Latest verify note:
    - `artifacts/verify/20260308_reviewer_exhaustiveness_prompt_engineering_verify_round8.md`
- Controlled experiment notes:
  - Controlled-variable evidence is recorded in `artifacts/verify/20260308_reviewer_exhaustiveness_prompt_protocol_control_experiment.md` and `artifacts/verify/20260308_reviewer_exhaustiveness_protocol_control_medium_small.json`.
  - Under identical frozen scope/context/provider settings, the exhaustive prompt protocol produced more actionable findings than the baseline prompt variant.
- Residual risks:
  - Fresh clean review evidence now exists at `artifacts/reviews/20260308_reviewer_exhaustiveness_prompt_engineering_review_round9_medium_summary.json`.
  - Reviewer exhaustiveness remains a prompt/protocol improvement, not a formal proof that providers will always emit maximally complete findings in one pass.
- Follow-on recommendation:
  - If the fresh clean review holds, use this protocol as the base for future reviewer-policy tuning and later compare `medium` vs `xhigh` audit roles on a repaired codebase rather than relaxing protocol requirements.
