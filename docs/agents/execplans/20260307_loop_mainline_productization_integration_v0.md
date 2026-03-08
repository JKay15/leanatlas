---
title: Productize LOOP as a LeanAtlas mainline system and align project-level docs/skills around it
owner: Codex (local workspace)
status: done
created: 2026-03-07
---

## Purpose / Big Picture
LeanAtlas has already absorbed substantial LOOP functionality into committed contracts, schemas, tools, tests, and maintainer workflows. The next productization wave should make that mainline reality explicit and usable. LOOP is the primary subject of this wave. Project-level integration updates are supporting work: they must align LeanAtlas entrypoints, workflow docs, skills, and indices with LOOP's mainline role, not dilute LOOP into a generic documentation cleanup theme. The goal is that a new maintainer can discover, understand, and use the current mainline LOOP path without reconstructing the 2026-03-05 to 2026-03-07 hardening cluster from chat history or experimental `.cache` notes.

## Glossary
- LOOP mainline productization: canonical user-facing/maintainer-facing documentation and skills for the already-landed LOOP system.
- Project-level integration: repository-level updates to status/workflow/index/skills entrypoints that make LOOP discoverable and correctly situated in LeanAtlas mainline.
- Bounded decoupling: clarifying `LOOP core` vs `LeanAtlas adapter` boundaries without attempting a full cross-repo extraction.
- Experimental asset classification: classify `.cache/leanatlas/tmp/**` assets into absorbed capability source, retained evidence/fixture input, or still-experimental-only material.

## Scope
In scope:
- document current mainline LOOP capabilities, boundaries, and entrypoints
- produce an authoritative `implemented / partial / planned` matrix for the mainline LOOP stack
- update LeanAtlas project-level docs/skills/indexes where needed so they accurately reflect LOOP as a mainline system
- classify relevant `.cache/leanatlas/tmp/**` LOOP/formalization assets for migration/mainline-use purposes
- bounded decoupling documentation: clarify `LOOP core` vs `LeanAtlas adapter` responsibilities

Out of scope:
- building unimplemented LOOP features such as batch supervisor/autopilot or reconciliation runtime
- extracting LOOP into a separate repository
- wholesale copying experiment directories into committed mainline paths
- unrelated project-wide doc cleanup not directly tied to LOOP-as-mainline integration

## Interfaces and Files
Expected focus areas:
- `docs/agents/LOOP_MAINLINE.md`
- `docs/agents/STATUS.md`
- `docs/agents/MAINTAINER_WORKFLOW.md`
- `docs/agents/OPERATOR_WORKFLOW.md`
- `docs/agents/README.md`
- `docs/agents/execplans/README.md`
- `docs/navigation/FILE_INDEX.md`
- `docs/testing/TEST_MATRIX.md`
- `.agents/skills/**`
- `docs/contracts/LOOP_*.md`
- `tools/loop/**`
- productized formalization surfaces already in mainline (`tools/formalization/**`, related contracts/tests) only insofar as they relate to the LOOP/mainline narrative

## Planned deliverables
- mainline LOOP capability matrix
- LOOP-first maintainer/operator usage entrypoints
- authoritative mainline entry doc: `docs/agents/LOOP_MAINLINE.md`
- a LOOP mainline skill for routing/usage discovery
- project-level docs/skills/index alignment around LOOP mainline adoption
- experimental-asset classification note for `.cache/leanatlas/tmp/**`
- explicit statement that LOOP is the primary subject of this wave
- explicit statement that project-level integration updates are supporting work

## Milestones
### 1) TDD guard for mainline entrypoints
Deliverables:
- a failing contract test requiring:
  - an authoritative `docs/agents/LOOP_MAINLINE.md`
  - project entry docs that point at it
  - a LOOP mainline skill indexed in `.agents/skills/README.md`

Commands:
- `uv run --locked python tests/contract/check_loop_mainline_docs_integration.py`

Acceptance:
- the new guard fails before the docs/skills integration lands

### 2) Productize LOOP as a project-level mainline entry
Deliverables:
- `docs/agents/LOOP_MAINLINE.md`
- an implemented/partial/planned capability matrix
- explicit `LOOP core` vs `LeanAtlas adapters` boundaries
- experimental asset classification for relevant `.cache/leanatlas/tmp/**` sources

Commands:
- `sed -n '1,260p' docs/agents/LOOP_MAINLINE.md`

Acceptance:
- a new maintainer can discover the current mainline LOOP surface without replaying the recent hardening cluster

### 3) Align project entry docs and skills
Deliverables:
- update `STATUS.md`, `README.md`, `MAINTAINER_WORKFLOW.md`, `OPERATOR_WORKFLOW.md`
- add/update the mainline LOOP skill and the skills index
- keep execplan/docs/testing/navigation indices synchronized

Commands:
- `uv run --locked python tests/contract/check_loop_mainline_docs_integration.py`
- `uv run --locked python tests/contract/check_skills_standard_headers.py`

Acceptance:
- project-level entrypoints now route users to LOOP as a mainline LeanAtlas system

### 4) Verification and FAST-only closeout
Deliverables:
- required verification and a FAST-only review over the final docs/skills state

Commands:
- `uv run --locked python tests/run.py --profile core`
- `uv run --locked python tests/run.py --profile nightly`
- `lake build`
- `git diff --check`

Acceptance:
- the minimum usable LOOP mainline productization layer lands with clean verification and FAST review evidence

## Testing plan
- new contract guard:
  - `tests/contract/check_loop_mainline_docs_integration.py`
- rerun:
  - `tests/contract/check_loop_mainline_productization_scope.py`
  - `tests/contract/check_execplan_readme_authority.py`
  - `tests/contract/check_loop_contract_docs.py` (only if LOOP contract wording is touched)
  - `tests/contract/check_skills_standard_headers.py`

## Decision log
- 2026-03-07: this wave is explicitly LOOP-first; project-level integration work exists to make LOOP usable as LeanAtlas mainline, not to dilute the subject.
- 2026-03-07: the minimum usable deliverable is an authoritative mainline entry doc plus a routable skill, not a full extraction of LOOP into a separate repository.
- 2026-03-07: `.cache/leanatlas/tmp/**` is classified for migration/evidence purposes; it is not a bulk copy source.

## Acceptance direction
- LOOP is the primary subject of the wave
- project-level integration updates are supporting work that help users find and use LOOP in LeanAtlas mainline
- the wave is not framed as a generic whole-project documentation sweep
- `.cache/leanatlas/tmp/**` is classified, not wholesale copied into mainline

## Outcomes & retrospective (fill when done)
- Completed:
  - added the canonical mainline entry doc `docs/agents/LOOP_MAINLINE.md`
  - documented an authoritative `implemented / partial / planned` matrix for the committed LOOP surface
  - documented `LOOP core` vs `LeanAtlas adapters` boundaries and `.cache/leanatlas/tmp/**` asset classification
  - aligned `STATUS.md`, `README.md`, `MAINTAINER_WORKFLOW.md`, and `OPERATOR_WORKFLOW.md` with LOOP as a LeanAtlas mainline system
  - added the routable mainline skill `.agents/skills/leanatlas-loop-mainline/SKILL.md` and indexed it in `.agents/skills/README.md`
  - synchronized `tests/manifest.json`, `docs/testing/TEST_MATRIX.md`, and `docs/navigation/FILE_INDEX.md`
- Verification:
  - targeted guards passed:
    - `uv run --locked python tests/contract/check_loop_mainline_docs_integration.py`
    - `uv run --locked python tests/contract/check_loop_mainline_productization_scope.py`
    - `uv run --locked python tests/contract/check_skills_standard_headers.py`
    - `uv run --locked python tests/contract/check_execplan_readme_authority.py`
    - `uv run --locked python tests/contract/check_test_registry.py`
    - `uv run --locked python tests/contract/check_test_matrix_up_to_date.py`
    - `uv run --locked python tests/contract/check_file_index_reachability.py`
  - required verification:
    - `uv run --locked python tests/run.py --profile core`
    - `uv run --locked python tests/run.py --profile nightly`
    - `lake build`
    - `git diff --check`
  - FAST review closeout:
    - round1 raised one actionable guard issue in `check_loop_mainline_docs_integration.py`
    - round2 returned `No findings.`
- Residual risks:
  - the mainline entry accurately distinguishes implemented vs partial vs planned capabilities, but the planned themes remain substantial follow-on work
  - `core` verification still exhibits unrelated intermittent cleanup races in some existing tests (`check_scenario_runner_plan_mode.py`, `check_problem_state_reconcile.py`), so this wave relies on isolated reruns when those flakes occur
- Follow-on recommendation:
  - keep the master batch plan active and continue with remaining staged themes rather than expanding this docs wave into broader new implementation work
