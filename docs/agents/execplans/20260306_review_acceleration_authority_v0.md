---
title: Execplan index authority fix and staged review acceleration helpers
owner: codex
status: done
created: 2026-03-06
---

## Purpose / Big Picture
The current `docs/agents/execplans/README.md` still presents a hand-maintained "Current plans" list that can drift away from the real active-plan state. That is misleading now that ExecPlan truth lives in per-file front matter and maintainer LOOP evidence. At the same time, the current maintainer review flow has already shown two high-ROI acceleration strategies: staged scope narrowing and reviewer-tier escalation. This plan fixes the misleading README authority boundary and productizes the acceleration pattern into deterministic helper APIs, tests, and maintainer-facing instructions that can be used tonight for worktree-split implementation without waiting for real runtime concurrency.

## Glossary
- authoritative ExecPlan state: the `status:` front matter in each ExecPlan file plus the corresponding maintainer LOOP/session evidence.
- staged narrowing: splitting a review scope into smaller deterministic partitions and narrowing follow-up review to the partitions or merged subset that still matter.
- pyramid reviewer: a review strategy that starts with faster/lower-cost reviewer tiers and escalates to slower/higher-thinking tiers only when needed.
- integrated closeout review: the final review round whose result is allowed to drive `AI_REVIEW_CLOSEOUT`.

## Scope
In scope:
- `docs/agents/execplans/README.md` authority wording and removal of misleading "Current plans" framing.
- deterministic helper APIs for scope partitioning and pyramid-review planning under `tools/loop/**`.
- contract/docs/test coverage for staged narrowing + pyramid reviewer semantics.
- a maintainer-facing skill for repeated use of the review-acceleration workflow.

Out of scope:
- real concurrent node execution in LOOP runtime.
- multi-worktree orchestration or supervisor reconciliation artifacts.
- changing provider CLI behavior or adding new providers.
- live `AI_REVIEW` strategy automation beyond deterministic plan/helper generation.

## Interfaces and Files
- `docs/agents/execplans/README.md`
  - remove misleading authoritative phrasing and point readers to front matter + maintainer evidence.
- `tools/loop/review_strategy.py`
  - deterministic scope partitioning and pyramid-review plan builders.
- `tools/loop/__init__.py`
  - export the new review strategy helpers.
- `docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md`
  - define staged narrowing / pyramid reviewer semantics and final integrated closeout rule.
- `docs/contracts/LOOP_PYTHON_SDK_CONTRACT.md`
  - document the maintainer-facing review strategy helper surface.
- `.agents/skills/leanatlas-loop-review-acceleration/SKILL.md`
  - reusable workflow for staged narrowing + pyramid reviewer.
- `.agents/skills/README.md`
  - register the new skill.
- `docs/agents/README.md`
  - add the new task-to-skill/doc entry.
- `tests/contract/check_execplan_readme_authority.py`
  - assert the README no longer presents a hand-maintained active-plan list as authoritative.
- `tests/contract/check_loop_review_strategy.py`
  - deterministic TDD for scope partitioning and pyramid-review plan semantics.
- `tests/contract/check_loop_contract_docs.py`
  - require the new contract snippets.
- `tests/contract/check_loop_python_sdk_contract_surface.py`
  - require the new helper surface if exported.
- `tests/contract/check_skills_standard_headers.py`
  - exercised automatically for the new skill.
- `tests/manifest.json`
  - register new tests.
- `docs/testing/TEST_MATRIX.md`
  - regenerate after manifest updates.

## Milestones
1) Red tests and authority boundary
- Deliverables:
  - add `tests/contract/check_execplan_readme_authority.py`
  - add `tests/contract/check_loop_review_strategy.py`
  - update existing contract/doc surface tests for the new semantics
- Commands:
  - `uv run --locked python tests/contract/check_execplan_readme_authority.py`
  - `uv run --locked python tests/contract/check_loop_review_strategy.py`
  - `uv run --locked python tests/contract/check_loop_contract_docs.py`
  - `uv run --locked python tests/contract/check_loop_python_sdk_contract_surface.py`
- Acceptance:
  - tests fail before implementation because README still looks authoritative and the helper surface/contract text does not yet exist.

2) Deterministic helper implementation
- Deliverables:
  - add `tools/loop/review_strategy.py`
  - update `tools/loop/__init__.py`
- Commands:
  - `uv run --locked python tests/contract/check_loop_review_strategy.py`
  - `uv run --locked python tests/contract/check_loop_python_sdk_contract_surface.py`
- Acceptance:
  - helpers deterministically partition scope files and build a pyramid-review plan.
  - low-tier staged rounds are marked non-terminal, while the final integrated round is the only closeout-eligible stage.

3) Docs/contracts/skill alignment
- Deliverables:
  - update `docs/agents/execplans/README.md`
  - update `docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md`
  - update `docs/contracts/LOOP_PYTHON_SDK_CONTRACT.md`
  - add `.agents/skills/leanatlas-loop-review-acceleration/SKILL.md`
  - update `.agents/skills/README.md`
  - update `docs/agents/README.md`
- Commands:
  - `uv run --locked python tests/contract/check_execplan_readme_authority.py`
  - `uv run --locked python tests/contract/check_loop_contract_docs.py`
  - `uv run --locked python tests/contract/check_skills_standard_headers.py`
- Acceptance:
  - README clearly says it is a non-authoritative index.
  - docs explain staged narrowing / pyramid reviewer without claiming real concurrency.
  - a maintainer can follow one committed skill to apply the acceleration strategy tonight.

4) Verification and maintainer LOOP closeout
- Deliverables:
  - fill outcomes in this plan
  - materialize maintainer LOOP evidence for this change
- Commands:
  - `uv run --locked python tests/contract/check_execplan_readme_authority.py`
  - `uv run --locked python tests/contract/check_loop_review_strategy.py`
  - `uv run --locked python tests/contract/check_loop_contract_docs.py`
  - `uv run --locked python tests/contract/check_loop_python_sdk_contract_surface.py`
  - `uv run --locked python tests/contract/check_skills_standard_headers.py`
  - `uv run --locked python tests/run.py --profile core`
  - `uv run --locked python tests/run.py --profile nightly`
  - `lake build`
  - `git diff --check`
- Acceptance:
  - targeted and full verification pass
  - maintainer LOOP session shows a completed `AI review node` and closeout for this change

## Testing plan (TDD)
- Add a deterministic README-authority contract test that rejects hand-maintained active-plan wording.
- Add a deterministic review-strategy contract test that checks:
  - scope normalization/partitioning is stable
  - partition IDs and fingerprints are deterministic
  - pyramid stages are ordered from fast to strict
  - low-tier stages are not closeout-eligible
  - final integrated stage is closeout-eligible and uses integrated scope
- Update contract-surface tests so the new helper surface and contract wording become mandatory.

## Decision log
- 2026-03-06: do not fold true concurrency into this plan; acceleration tonight comes from better partitioning and reviewer staging, not from runtime scheduler changes.
- 2026-03-06: make staged narrowing and pyramid review first-class maintainer aids, not just prompt folklore.
- 2026-03-06: keep final `AI_REVIEW_CLOSEOUT` tied to an integrated closeout review; partitioned low-tier rounds are advisory/triage aids only.
- 2026-03-06: replaying helper-derived merged scope alongside the same `followup_partition_ids` must preserve provenance metadata and `strategy_fingerprint`; helper replay is not a manual override.

## Rollback plan
- Revert:
  - `docs/agents/execplans/README.md`
  - `tools/loop/review_strategy.py`
  - `tools/loop/__init__.py`
  - `docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md`
  - `docs/contracts/LOOP_PYTHON_SDK_CONTRACT.md`
  - `.agents/skills/leanatlas-loop-review-acceleration/SKILL.md`
  - `.agents/skills/README.md`
  - `docs/agents/README.md`
  - `tests/contract/check_execplan_readme_authority.py`
  - `tests/contract/check_loop_review_strategy.py`
  - `tests/manifest.json`
  - `docs/testing/TEST_MATRIX.md`
- Re-run the targeted tests above to confirm rollback.

## Outcomes & retrospective (fill when done)
- `docs/agents/execplans/README.md` now states it is a non-authoritative index and points auditors to per-plan `status:` front matter plus maintainer LOOP/session evidence.
- Deterministic review-acceleration helpers landed under `tools/loop/review_strategy.py` and are exported from `tools/loop/__init__.py`:
  - `partition_review_scope_paths(...)`
  - `merge_partition_scope_paths(...)`
  - `build_pyramid_review_plan(...)`
- Helper semantics now cover:
  - explicit selected follow-up partitions
  - inferred file-level effective scope
  - manual file-level narrowing
  - explicit no-escalation with `followup_partition_ids=[]`
  - explicit no-escalation with `followup_partition_ids=[]` plus `effective_scope_paths=[]`
  - helper replay of merged effective scope without provenance/fingerprint drift
- `docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md` and `docs/contracts/LOOP_PYTHON_SDK_CONTRACT.md` now document staged narrowing and pyramid reviewer as deterministic planning aids only, not proof of real runtime concurrency.
- A maintainer-facing skill now exists at `.agents/skills/leanatlas-loop-review-acceleration/SKILL.md`, and related indices/docs are updated so tonight's worktree-split implementation can reuse the same staged narrowing and pyramid-review workflow.
- Verification completed on the final state:
  - targeted contract checks for README authority, review strategy, contract docs, SDK surface, wave execution policy, and skills headers
  - `uv run --locked python tests/run.py --profile core`
  - `uv run --locked python tests/run.py --profile nightly`
  - `lake build`
  - `git diff --check`
- Maintainer LOOP closeout passed for the final state:
  - run key: `292a4c34d393869ede39639745468eacc93fed352b9508c166ad3f1b0a651393`
  - final review: `artifacts/reviews/20260306_review_acceleration_authority_review_round8_response.md`
  - graph summary: `artifacts/loop_runtime/by_key/292a4c34d393869ede39639745468eacc93fed352b9508c166ad3f1b0a651393/graph/GraphSummary.jsonl`
- Deferred by design:
  - true runtime concurrency
  - multi-worktree orchestration / supervisor reconciliation
  - automatic execution of pyramid-review stages beyond deterministic helper generation
