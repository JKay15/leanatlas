---
title: Productize formalization ingress and enrichment helpers from experimental paper workflows into LeanAtlas mainline
owner: Codex (local workspace)
status: done
created: 2026-03-08
---

## Purpose / Big Picture
LeanAtlas already absorbed the deterministic formalization core from the paper experiments, but several high-value front-end helpers still live only under `.cache/leanatlas/tmp/theorem_proof_proto_v0_2/**` and `.cache/leanatlas/tmp/arxiv_2112_13254v3_proto_v0_3/**`. Those helpers are now the highest-value remaining gap for real-paper usability: human-provided external sources are not yet first-class, LaTeX/PDF enrichment is not yet on the canonical path, mapping triage remains mostly paper-local, and annotation reverse-link resync still depends on experimental scripts. This plan productizes the bounded P1-P4 subset into committed tools/contracts/tests/docs so paper formalization can start from a mainline path instead of reconstructing experiment glue from `.cache`. The goal is capability absorption, not experiment-directory copying.

## Glossary
- ExternalSourcePack: machine-readable bundle of user-provided source files plus deterministic retrieval/enrichment metadata for external dependencies.
- Human ingress: explicit formalization input supplied by a human outside the current run; it must be published as evidence rather than hidden in chat state.
- Source enrichment: deterministic augmentation of a formalization ledger using LaTeX/PDF-derived equation and citation information.
- Mapping triage: deterministic prioritization and reporting of which claim/clause/atom/anchor mappings still need review.
- Reverse-link resync: deterministic refresh of annotation-backed `lean_reverse_links` / anchor alignment after Lean source edits.

## Scope
In scope:
- absorb P1-P4 experimental capabilities into committed mainline tools/docs/tests:
  - ExternalSourcePack + human ingress
  - LaTeX/PDF enrichment
  - mapping triage / review todo generation
  - annotation reverse-link resync
- update formalization contracts/schemas/docs where the canonical surface changes
- add deterministic tests for the new mainline surfaces
- document how these helpers relate to the existing formalization governor/worklist path

Out of scope:
- batch supervisor/autopilot
- review supersession/reconciliation runtime
- full formalization-cycle orchestration replacement for `run_formalization_cycle_v04.sh`
- paper-specific ledgers/reports under `.cache/**`
- broad extraction of LOOP into a separate repository

Allowed directories:
- `tools/formalization/**`
- `tools/workflow/**` (only if helper integration requires a thin routing hook)
- `docs/contracts/**`
- `docs/schemas/**`
- `docs/agents/**`
- `docs/testing/**`
- `docs/navigation/**`
- `tests/**`
- `.agents/skills/**`
- `docs/agents/execplans/**`

Forbidden directories:
- `.cache/leanatlas/tmp/**` as an implementation target
- `LeanAtlas/**`
- `Problems/**`

## Interfaces and Files
Experimental sources to absorb from:
- `.cache/leanatlas/tmp/theorem_proof_proto_v0_2/enrich_ledger_from_latex_v03.py`
- `.cache/leanatlas/tmp/theorem_proof_proto_v0_2/generate_review_todo_v03.py`
- `.cache/leanatlas/tmp/theorem_proof_proto_v0_2/resync_annotation_reverse_links_v03.py`
- `.cache/leanatlas/tmp/arxiv_2112_13254v3_proto_v0_3/build_external_source_pack_v04.py`
- `.cache/leanatlas/tmp/arxiv_2112_13254v3_proto_v0_3/ExternalSourcePack.v0_4.schema.json`
- `.cache/leanatlas/tmp/arxiv_2112_13254v3_proto_v0_3/external_user_inputs.template.v0_4.json`

Expected committed targets:
- `tools/formalization/external_source_pack.py`
- `tools/formalization/source_enrichment.py`
- `tools/formalization/review_todo.py`
- `tools/formalization/resync_reverse_links.py`
- `docs/contracts/FORMALIZATION_LEDGER_CONTRACT.md`
- `docs/contracts/FORMALIZATION_GOVERNANCE_CONTRACT.md`
- `docs/schemas/ExternalSourcePack.schema.json` (or a committed schema equivalent if naming is adjusted)
- `docs/agents/LOOP_MAINLINE.md`
- `docs/agents/STATUS.md`
- `docs/agents/MAINTAINER_WORKFLOW.md`
- `.agents/skills/leanatlas-loop-mainline/SKILL.md`
- `tests/contract/check_formalization_frontier_absorption.py`

## Milestones
### 1) TDD freeze for absorbed formalization-frontier surfaces
Deliverables:
- a new red contract test covering the committed surface for:
  - external source pack / human ingress
  - source enrichment
  - review todo generation
  - reverse-link resync

Commands:
- `uv run --locked python tests/contract/check_formalization_frontier_absorption.py`

Acceptance:
- the new test fails before implementation and describes the intended mainline surface precisely enough to block drift back into `.cache`-only usage

### 2) Productize ExternalSourcePack + human ingress
Deliverables:
- committed mainline tool/module for building/validating external-source packs
- committed schema/contract wording for human-provided external inputs as explicit evidence
- usage docs showing where this enters the formalization path

Commands:
- `uv run --locked python tests/contract/check_formalization_frontier_absorption.py`
- `uv run --locked python tests/contract/check_formalization_schema_policy.py`

Acceptance:
- a maintainer can feed bounded external source inputs through a committed mainline interface without reaching into experiment scripts

### 3) Productize source enrichment + mapping triage + reverse-link resync
Deliverables:
- committed enrichment tool(s) for LaTeX/PDF augmentation
- committed mapping-triage/review-todo tool(s)
- committed annotation reverse-link resync tool
- docs/contracts updated so these are clearly canonical helpers rather than paper-local scripts

Commands:
- `uv run --locked python tests/contract/check_formalization_frontier_absorption.py`
- `uv run --locked python tests/contract/check_formalization_toolchain_runtime.py`

Acceptance:
- the three helper families are available from committed mainline paths and can be referenced from formalization workflow docs without pointing into `.cache`

### 4) Mainline routing/docs/skills integration
Deliverables:
- update LOOP/mainline/formalization docs to route users to the new helpers
- update skill/index material if a maintainer needs a new mainline routing step
- classify the experimental source files as absorbed capability sources after landing

Commands:
- `uv run --locked python tests/contract/check_loop_mainline_docs_integration.py`
- `uv run --locked python tests/contract/check_skills_standard_headers.py`

Acceptance:
- a new maintainer can discover the committed formalization-frontier path from mainline docs/skills, without treating `.cache` scripts as the default path

### 5) Verification and FAST-only closeout
Deliverables:
- required verification and a FAST-only final review over the final implementation state

Commands:
- `uv run --locked python tests/run.py --profile core`
- `uv run --locked python tests/run.py --profile nightly`
- `lake build`
- `git diff --check`

Acceptance:
- the absorbed helper surfaces land with clean verification and FAST review evidence

## Testing plan (TDD)
New tests:
- `tests/contract/check_formalization_frontier_absorption.py`
  - external-source pack surface exists and is documented
  - source enrichment surface exists and is documented
  - mapping triage surface exists and is documented
  - reverse-link resync surface exists and is documented

Regression checks:
- `tests/contract/check_formalization_schema_policy.py`
- `tests/contract/check_formalization_toolchain_runtime.py`
- `tests/contract/check_loop_mainline_docs_integration.py`
- `tests/contract/check_skills_standard_headers.py`

Contamination control:
- all generated data must remain under temporary directories, `.cache/leanatlas/**`, or `artifacts/**`
- no experiment assets under `.cache/leanatlas/tmp/**` are modified in place

## Decision log
- This wave is bounded: it absorbs the four highest-value formalization-frontier helpers without reopening the larger autopilot/reconciliation batch.
- The implementation target is committed mainline capability, not a file copy of experimental paper workspaces.
- Human-provided external inputs must become explicit evidence artifacts, not hidden prompt-only context.
- Paper-specific ledgers, reports, and local `lean_work/**` remain evidence/fixture material unless a later plan explicitly productizes them.

## Rollback plan
- Revert newly added formalization-frontier helper modules, docs, and tests:
  - `tools/formalization/**` additions from this wave
  - associated contract/schema/doc updates
  - `tests/contract/check_formalization_frontier_absorption.py`
- verify rollback with:
  - `uv run --locked python tests/contract/check_formalization_schema_policy.py`
  - `uv run --locked python tests/run.py --profile core`

## Outcomes & retrospective (fill when done)
- Completed:
  - absorbed ExternalSourcePack + explicit human ingress into committed mainline tools/contracts/schema
  - absorbed deterministic LaTeX/Bib source enrichment for equation/citation augmentation
  - absorbed deterministic mapping triage / review todo generation
  - absorbed deterministic annotation reverse-link resync from `.lean` annotations
  - updated mainline docs/skills/indexes so maintainers can find these helpers without treating `.cache` scripts as the default path
- Verification:
  - `uv run --locked python tests/contract/check_formalization_frontier_absorption.py`
  - `uv run --locked python tests/contract/check_formalization_schema_policy.py`
  - `uv run --locked python tests/contract/check_formalization_toolchain_runtime.py`
  - `uv run --locked python tests/contract/check_formalization_governor_policy_contract.py`
  - `uv run --locked python tests/contract/check_loop_mainline_docs_integration.py`
  - `uv run --locked python tests/contract/check_skills_standard_headers.py`
  - `uv run --locked python tests/determinism/check_canonical_json.py`
  - `uv run --locked python tests/run.py --profile core` (one profile run hit an existing `check_problem_state_reconcile.py` tmp-path race; isolated rerun passed)
  - `uv run --locked python tests/run.py --profile nightly` (one profile run hit an existing `check_scenario_tool_reuse_scoring.py` tmp-cleanup race; isolated rerun passed)
  - `lake build`
  - `git diff --check`
- Residual risks:
  - ExternalSourcePack committed MVP is intentionally local/user-ingress first; network retrieval providers are not yet productized
  - source enrichment currently focuses on deterministic LaTeX/Bib augmentation and does not replace heavier paper-specific extractors
- Follow-on recommendation:
  - continue with `P5` bounded autofill/seed extraction and later a fuller front-end orchestrator only after review reconciliation and broader LOOP automation mature
