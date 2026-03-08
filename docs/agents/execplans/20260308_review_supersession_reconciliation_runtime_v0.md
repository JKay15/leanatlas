---
title: Implement full review supersession / reconciliation runtime and evaluate pure-medium reviewer viability
owner: Codex (local workspace)
status: done
created: 2026-03-08
parent_execplan: docs/agents/execplans/20260307_loop_core_parallel_nested_batch_v0.md
---

## Purpose / Big Picture
The current LOOP mainline already compiles `finding_dedupe` and reconciliation metadata into review orchestration bundles, but the authoritative runtime/evidence engine that actually tracks superseded findings, reconciles multi-round reviewer output, and feeds a settled finding set into final closeout does not exist yet. That leaves a gap between staged review contracts and real execution.

This plan closes that gap with the full review supersession / reconciliation runtime, not a bounded MVP. At the same time, it serves as the first deliberate `medium`-reviewer trial on an unimplemented core LOOP feature. The evaluation question remains practical: can `pure medium` reviewer close a small-scope, high-risk review/reconciliation feature with materially better signal than `low`, while still staying cheap enough to replace the older `STRICT / xhigh` default path for most serious but bounded work?

## Why this is the right medium trial
- The feature is still unimplemented, so the reviewer is not grading a solved surface.
- The logic is core enough that `medium` should have a chance to show stronger value than `low`.
- The scope is much smaller than `batch supervisor / autopilot`, so the experiment is cost-bounded.
- The output will directly benefit current `FAST` and staged-review workflows.

## Glossary
- `supersession`: a newer review round explicitly covers or invalidates an older round for the same review scope.
- `reconciliation runtime`: the deterministic engine that ingests review findings and emits authoritative finding dispositions.
- `authoritative finding ledger`: immutable by-digest evidence describing each known finding and whether it is `CONFIRMED`, `DISMISSED`, or `SUPERSEDED`, paired with an append-only persistence journal.
- `medium trial`: this wave's policy of using only `medium` reviewer for implementation closeout, without escalating to `STRICT / xhigh`.

## Scope
In scope:
- materialize a deterministic reconciliation artifact and runtime surface for staged review findings
- support authoritative dispositions:
  - `CONFIRMED`
  - `DISMISSED`
  - `SUPERSEDED`
- define stable finding identity / lineage for review rounds that share a review scope
- reconcile findings across:
  - repeated rounds over the same effective scope
  - staged `FAST/DEEP/STRICT` review bundles
  - multiple partitions that later converge into an integrated closeout
- make final closeout consume the reconciled finding set instead of implicit raw reviewer output
- persist machine-readable reconciliation evidence that later runtime stages can consume without re-reading raw review output
- run this implementation wave with `pure medium` reviewer to evaluate quality/cost tradeoff

Out of scope:
- batch supervisor / autopilot
- cross-worktree/global integration reconciliation beyond a single repository execution context
- speculative fully concurrent reviewer arbitration outside the deterministic reconciliation rules defined in this wave
- changing the global default reviewer policy again before the medium trial evidence is collected

## Interfaces and Files
- `docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md`
- `docs/contracts/LOOP_PYTHON_SDK_CONTRACT.md`
- `docs/agents/LOOP_MAINLINE.md`
- `docs/agents/execplans/20260307_loop_core_parallel_nested_batch_v0.md`
- `docs/agents/execplans/README.md`
- `tools/loop/review_orchestration.py`
- `tools/loop/runtime.py`
- `tools/loop/review_runner.py`
- `tests/contract/check_loop_review_orchestration.py`
- new runtime-facing reconciliation tests under `tests/contract/`

## Milestones
1) Freeze full reconciliation-runtime acceptance in tests
- Deliverables:
  - new deterministic tests that fail until a reconciliation runtime exists
  - explicit checks for `CONFIRMED | DISMISSED | SUPERSEDED`
  - explicit checks for supersession lineage and integrated-closeout consumption
- Acceptance:
  - tests describe the full runtime gap rather than only bundle metadata

2) Land the deterministic reconciliation runtime
- Deliverables:
  - stable finding identity / lineage
  - immutable by-digest reconciliation ledger plus append-only journal
  - final closeout consumes reconciled findings
  - staged review follow-up can read authoritative dispositions instead of ad hoc/manual merge results
- Acceptance:
  - staged review workflows no longer rely on implicit/manual finding merge

3) Align contracts/docs/runtime surfaces with authoritative reconciliation
- Deliverables:
  - contract wording updated so supersession/reconciliation is no longer merely a staged-bundle concept
  - runtime-facing documentation points to the authoritative ledger/artifact
- Acceptance:
  - docs, contracts, and runtime surfaces describe the same settled finding model

4) Evaluate `medium` reviewer on the implementation wave
- Deliverables:
  - review artifacts recorded with `agent_profile = gpt-5.4-medium`
  - comparison note: `medium` signal/cost vs prior `low`-only waves
- Acceptance:
  - the wave closes with `medium` only, or clearly records why medium was insufficient

## Testing plan (TDD)
- add deterministic runtime tests first
- rerun:
  - `uv run --locked python tests/contract/check_loop_review_orchestration.py`
  - `uv run --locked python tests/contract/check_loop_contract_docs.py`
  - `uv run --locked python tests/contract/check_loop_python_sdk_contract_surface.py`
  - `uv run --locked python tests/contract/check_loop_wave_execution_policy.py`
  - `uv run --locked python tests/run.py --profile core`
  - `uv run --locked python tests/run.py --profile nightly`
  - `lake build`

## Decision log
- 2026-03-08: pick full review supersession / reconciliation runtime as the first pure-medium reviewer trial because it is core, still unimplemented, and directly determines whether staged review results can become authoritative runtime evidence.
- 2026-03-08: do not reopen `STRICT / xhigh` as the default path during this trial; the trial exists precisely to test whether `medium` can occupy the serious-review middle tier.

## Rollback plan
- revert the new reconciliation runtime/test/docs changes
- preserve the plan and review evidence so the medium-trial result remains auditable

## Outcomes & retrospective (fill when done)
- Implemented the full deterministic `review supersession / reconciliation runtime` in `tools/loop/review_reconciliation.py`.
- Landed the authoritative schema at `docs/schemas/ReviewSupersessionReconciliation.schema.json` and wired exports/tests/contracts around it.
- Added runtime coverage for:
  - `CONFIRMED | DISMISSED | SUPERSEDED` settlement
  - scope-lineage separation when unrelated rounds reuse the same `finding_key`
  - rejection of supersession records whose superseding round is not newer
  - run-key-independent immutable ledger persistence plus run-key-scoped append-only journals
- Pure-medium reviewer trial outcome:
  - round1 medium surfaced 3 real issues (authoritative timestamp determinism, unrelated-scope grouping, older-superseder acceptance)
  - round2 medium surfaced 1 real issue (immutable ledger path still tied to `run_key`)
  - round3 medium returned `No findings.` on the post-fix implementation state
- Historical implementation closeout authority for this wave remains the stable alias `artifacts/loop_runtime/by_execplan/docs__agents__execplans__20260308_review_supersession_reconciliation_runtime_v0.md__6f0765683810/MaintainerCloseoutRef.json`.
- Practical result: `medium` closed the implementation phase of this core reconciliation feature with four real findings across two implementation rounds and a clean implementation-state review. Later wording/authority repairs on current head belong to the active 20260308 repair wave rather than the historical closeout alias above, so any current-head reviewer-policy conclusion must wait on that repair wave's reduced xhigh recheck rather than being inferred from this historical closeout note alone.
