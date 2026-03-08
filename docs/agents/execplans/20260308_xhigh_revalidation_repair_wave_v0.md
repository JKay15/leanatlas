---
title: Repair wave for fresh xhigh revalidation findings, then bounded xhigh recheck and policy hardening
owner: Codex (local workspace)
status: active
created: 2026-03-08
parent_execplan: docs/agents/execplans/20260307_loop_core_parallel_nested_batch_v0.md
---

## Purpose / Big Picture
The fresh `gpt-5.4-xhigh` revalidation matrix reopened 9 / 9 previously closed targets, including P1 correctness defects in the shared formalization/user-preferences final scope and replay/provenance defects in the default reviewer-policy path. This wave is a repair-and-hardening pass, not a feature-expansion wave. The job is:

1. repair the smallest shared set of real defects that explains the reopen set,
2. rerun a reduced fresh `xhigh` audit on the highest-signal targets,
3. only if that reduced audit is clean, land the committed reviewer-policy hardening and low-frequency `xhigh` automation surfaces.

This ExecPlan must remain self-contained and executable from repository state alone. It must not depend on prior thread memory.

## Scope
In scope:
- formalization frontier correctness repairs exposed by fresh `xhigh`
- replay/provenance/backward-compatibility repairs for staged review orchestration
- onboarding/default-policy/mainline doc drift that affects authoritative routing or promised gates
- maintainer/runtime contract-test gaps and legacy replay backfill gaps
- reduced fresh `xhigh` revalidation on the highest-signal target subset
- conditional reviewer-policy hardening and low-frequency `xhigh` automation after the reduced set is clean

Out of scope:
- unrelated LOOP feature expansion
- autopilot/worktree/decoupling themes
- broad product redesign beyond the reopened findings
- policy wording that declares `xhigh` non-default before the reduced recheck is actually clean

## Root-cause clusters
### A) Formalization frontier correctness
Fresh `xhigh` reopened two targets over the same authoritative final scope because the committed helpers are not schema/behavior aligned:
- `tools/formalization/review_todo.py`
  - treats `atom_mappings[*].evidence` like a dict even though the schema/adapter emits a list
  - converts schema-valid `mismatch_kind = null` into the string `"None"` and falsely scores it as a mismatch
- `tools/formalization/source_enrichment.py`
  - citation-key matching can collide on same-author/same-year entries without title/text disambiguation
  - PDF-only reruns preserve old citation keys but overcount current-run hit totals

This cluster is highest priority because it contains real correctness bugs, not just stale docs.

### B) Review strategy / replay / provenance
Fresh `xhigh` reopened the tiered-policy/orchestration surfaces because current helper/runtime behavior does not fully match the committed replay story:
- `tools/loop/review_strategy.py`
  - default helper cannot materialize the documented explicit low-closeout path
- `tools/loop/review_orchestration.py`
  - authoritative replay now rejects historical strategy-plan artifacts that predate the newer provenance fields

This cluster blocks any credible claim that `FAST + low` baseline plus `medium` standard escalation is already stably productized.

### C) Mainline authority / onboarding / contract drift
Fresh `xhigh` also reopened several doc/skill targets because authoritative routing text and hard-gate promises drifted:
- `.agents/skills/leanatlas-onboard/SKILL.md`
- `docs/agents/execplans/README.md`
- `docs/agents/README.md`
- `docs/agents/STATUS.md`
- relevant done ExecPlans whose retrospective text no longer matches current head

This cluster is lower risk than A/B for runtime correctness, but it directly affects whether a fresh maintainer can discover and use the right LOOP path without prior thread context.

### D) Maintainer replay / closeout evidence drift
Fresh `xhigh` reopened maintainer/core surfaces because coverage and compatibility are incomplete:
- `tests/contract/check_loop_python_sdk_contract_surface.py` does not pin the committed `serial(...)`, `parallel(...)`, and `nested(...)` composition helpers strongly enough
- `tools/loop/maintainer.py` replay/backfill still misses legacy sidecar normalization for historical `scheduler.jsonl` / `nested_lineage.jsonl`

## Repair order
1. Fix cluster A first with TDD.
2. Fix cluster B next, including backward-compatible replay of historical strategy-plan artifacts.
3. Fix cluster D shared runtime/test gaps.
4. Fix cluster C authoritative doc/skill drift.
5. Run targeted verification plus required full verification.
6. Run reduced fresh `xhigh` revalidation on:
   - `docs/agents/execplans/20260307_review_orchestration_automation_v0.md`
   - `docs/agents/execplans/20260308_review_supersession_reconciliation_runtime_v0.md`
   - `docs/agents/execplans/20260308_formalization_enrichment_absorption_v0.md`
   - `docs/agents/execplans/20260308_loop_user_preferences_and_onboarding_defaults_v0.md`
7. Only if that reduced set is clean, land reviewer-policy hardening and low-frequency `xhigh` automation.

## Interfaces and Files
Primary repair surfaces:
- `tools/formalization/review_todo.py`
- `tools/formalization/source_enrichment.py`
- `tools/loop/review_strategy.py`
- `tools/loop/review_orchestration.py`
- `tools/loop/maintainer.py`
- `.agents/skills/leanatlas-onboard/SKILL.md`
- `docs/agents/execplans/README.md`
- `docs/agents/README.md`
- `docs/agents/STATUS.md`
- `docs/contracts/FORMALIZATION_LEDGER_CONTRACT.md`
- `docs/contracts/LOOP_PYTHON_SDK_CONTRACT.md`
- `tests/contract/check_formalization_frontier_absorption.py`
- `tests/contract/check_formalization_toolchain_runtime.py`
- `tests/contract/check_loop_review_strategy.py`
- `tests/contract/check_loop_review_orchestration.py`
- `tests/contract/check_loop_python_sdk_contract_surface.py`
- `tests/contract/check_loop_mainline_docs_integration.py`

Conditional policy-hardening/automation surfaces, only after reduced xhigh clean:
- `tools/loop/user_preferences.py`
- `docs/agents/ONBOARDING.md`
- `docs/setup/QUICKSTART.md`
- `docs/agents/LOOP_MAINLINE.md`
- `.agents/skills/leanatlas-loop-mainline/SKILL.md`
- `.agents/skills/leanatlas-loop-review-acceleration/SKILL.md`
- `docs/agents/AUTOMATIONS.md`
- `automations/registry.json`
- automation tests and onboarding contract checks touched by the final hardening scope

## Milestones
### 1) Freeze repair-wave scope and materialize maintainer LOOP session
Deliverables:
- this ExecPlan
- a fresh maintainer LOOP session for the repair wave before code changes

Acceptance:
- repair work closes through a new maintainer session rooted at this plan, not the earlier audit-only session

### 2) TDD for formalization frontier correctness
Deliverables:
- new/extended contract coverage for:
  - schema-valid `null mismatch_kind`
  - clause/binding issue attachment through list-shaped evidence
  - same-author/same-year citation-key disambiguation
  - PDF-only rerun hit accounting

Commands:
- `uv run --locked python tests/contract/check_formalization_frontier_absorption.py`
- `uv run --locked python tests/contract/check_formalization_toolchain_runtime.py`

Acceptance:
- tests fail before implementation and pin the exact reopened behaviors

### 3) TDD for strategy replay and maintainer/runtime compatibility
Deliverables:
- new/extended contract coverage for:
  - explicit low-closeout helper path
  - backward-compatible replay of older strategy-plan artifacts
  - legacy maintainer replay/backfill for missing sidecars
  - stronger SDK surface pinning for `serial/parallel/nested`

Commands:
- `uv run --locked python tests/contract/check_loop_review_strategy.py`
- `uv run --locked python tests/contract/check_loop_review_orchestration.py`
- `uv run --locked python tests/contract/check_loop_python_sdk_contract_surface.py`

Acceptance:
- tests fail before implementation and distinguish real backward-compatibility gaps from doc-only drift

### 4) Implement clustered repairs
Deliverables:
- repaired formalization helpers
- repaired strategy/replay/backfill behavior
- repaired authoritative docs/skills/retrospectives needed for clean recheck scope

Acceptance:
- no unrelated feature work is mixed into the patch

### 5) Verification
Required commands:
- `uv run --locked python tests/run.py --profile core`
- `uv run --locked python tests/run.py --profile nightly`
- `lake build`
- `git diff --check`

Targeted commands:
- `uv run --locked python tests/contract/check_formalization_frontier_absorption.py`
- `uv run --locked python tests/contract/check_formalization_toolchain_runtime.py`
- `uv run --locked python tests/contract/check_loop_review_strategy.py`
- `uv run --locked python tests/contract/check_loop_review_orchestration.py`
- `uv run --locked python tests/contract/check_loop_python_sdk_contract_surface.py`
- `uv run --locked python tests/contract/check_loop_mainline_docs_integration.py`
- onboarding/defaults/automation-targeted checks if policy hardening lands

Acceptance:
- verification is green on the settled repair state before any fresh reduced `xhigh` conclusion

### 6) Reduced fresh xhigh revalidation
Deliverables:
- fresh `gpt-5.4-xhigh` prompt/response/summary/canonical/attempt evidence for the reduced target set
- a short reduced-matrix verify note under `artifacts/verify/`

Acceptance:
- if any of the four reduced targets still reopens, stop and do not land policy hardening or new automation defaults

### 7) Conditional reviewer-policy hardening and low-frequency xhigh automation
Precondition:
- Milestone 6 reduced fresh `xhigh` set is clean

Deliverables:
- committed reviewer policy remains:
  - `FAST + low` baseline
  - `medium` standard escalation
  - `xhigh` exception-only
- low-frequency read-only `xhigh` audit automation targeting high-risk historical implementations
- onboarding/defaults surface exposes whether that automation is enabled and its bounded cadence without forcing raw RRULE details into bootstrap

Acceptance:
- the hardening wave does not make `xhigh` the daytime default path

## TDD / verification notes
- Use `apply_patch` for all manual edits.
- Keep generated/temporary test data under temp directories or `.cache/leanatlas/**`.
- Do not repair findings by rewriting historical review artifacts; fix code/docs/contracts/tests at current head, then generate fresh evidence.

## Decision log
- 2026-03-08: repair must be clustered by shared root cause, not by mechanically editing 9 reopened ExecPlans independently.
- 2026-03-08: formalization correctness and replay compatibility outrank policy wording.
- 2026-03-08: reviewer-policy hardening and low-frequency `xhigh` automation are conditional follow-ons, not part of the initial repair gate.

## Rollback plan
- revert only the repair-wave edits from this plan
- rerun the targeted contract checks above plus `uv run --locked python tests/run.py --profile core`
- preserve the fresh audit artifacts so reopened evidence is not lost even if the repair patch is backed out

## Outcomes & retrospective (fill when done)
- Pending.
