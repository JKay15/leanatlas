---
title: Stage LOOP skills decoupling and LeanAtlas project-level skills governance/completeness
owner: Codex (local workspace)
status: planned
created: 2026-03-08
parent_execplan: docs/agents/execplans/20260307_loop_core_parallel_nested_batch_v0.md
---

## Purpose / Big Picture
LOOP now has committed mainline docs, contracts, tools, and several LeanAtlas-hosted skills. That is enough for current repository use, but not enough for either of the following goals:

1) treating LOOP as a reusable capability outside LeanAtlas, and
2) keeping LeanAtlas's own skill layer coherent as LOOP, formalization, and workflow surfaces continue to expand.

Today, the repository has usable LOOP skills, but they are still strongly LeanAtlas-branded and role-coupled (`leanatlas-loop-*`). At the same time, project-level skill completeness is only partially enforced through ad hoc integration updates. This plan makes both requirements explicit: LOOP skills must eventually split into reusable/core-facing skills and LeanAtlas adapter skills, and LeanAtlas needs a bounded but explicit project-level skills governance/completeness pass rather than relying on chance alignment.

## Scope
In scope:
- define which current LOOP skills are:
  - reusable LOOP-core skill material
  - LeanAtlas-specific adapter/workflow skill material
- define the future split between generic LOOP skills and `leanatlas-*` adapter skills
- define project-level skill governance/completeness requirements for LeanAtlas as LOOP and formalization capabilities grow
- define how skill indices, entry docs, and workflow docs stay aligned

Out of scope:
- implementing the full skill split in this planning wave
- renaming every existing skill immediately
- broad KB mining unrelated to LOOP/formalization/workflow adoption

## Current problem statement
Current committed LOOP skills are:
- `.agents/skills/leanatlas-loop-mainline/SKILL.md`
- `.agents/skills/leanatlas-loop-maintainer-ops/SKILL.md`
- `.agents/skills/leanatlas-loop-review-acceleration/SKILL.md`

These are sufficient for LeanAtlas mainline usage, but insufficient for standalone LOOP reuse because:
- names and routing are LeanAtlas-branded
- they assume LeanAtlas-specific `MAINTAINER` / `OPERATOR` workflow framing
- they route through LeanAtlas docs rather than standalone library docs/examples

Project-wide, LeanAtlas also lacks one explicit authoritative plan that says which new capabilities MUST gain:
- a skill
- only KB/docs
- or no skill at all

## Required future split
The long-term skill model must distinguish:

1) Reusable LOOP skills
- library/mainline orientation for non-LeanAtlas consumers
- generic review-orchestration usage
- generic loop/session/runtime usage
- generic closeout/evidence usage where role-neutral

2) LeanAtlas adapter skills
- `MAINTAINER` workflow usage
- `OPERATOR` workflow usage
- LeanAtlas-specific review policies
- LeanAtlas-specific worktree/orchestration/formalization routing

## Interfaces and Files
- `.agents/skills/**`
- `.agents/skills/README.md`
- `docs/agents/README.md`
- `docs/agents/LOOP_MAINLINE.md`
- `docs/agents/MAINTAINER_WORKFLOW.md`
- `docs/agents/OPERATOR_WORKFLOW.md`
- `docs/agents/kb/**`
- `docs/contracts/SKILLS_GROWTH_CONTRACT.md`
- `docs/agents/execplans/20260308_loop_python_library_decoupling_packaging_v0.md`

## Milestones
1) Freeze the skill-boundary matrix
- Deliverables:
  - authoritative classification of current LOOP skills into:
    - reusable LOOP-core candidates
    - LeanAtlas adapter skills
    - project-only skills that should remain outside LOOP reuse
- Acceptance:
  - the project no longer assumes current `leanatlas-loop-*` skills are automatically suitable for standalone LOOP reuse

2) Stage LOOP skill decoupling requirements
- Deliverables:
  - define which future generic LOOP skills must exist for the extracted library
  - define how current `leanatlas-loop-*` skills will map to:
    - generic LOOP skills
    - LeanAtlas-specific wrappers/adapters
- Acceptance:
  - code/library decoupling is explicitly paired with skill decoupling, not treated as docs-only reuse

3) Stage LeanAtlas project-level skills governance/completeness requirements
- Deliverables:
  - define when a new capability MUST ship with:
    - a skill
    - only KB/docs
    - no new skill
  - define required sync points:
    - `.agents/skills/README.md`
    - `docs/agents/README.md`
    - workflow entry docs
    - relevant mainline entry docs
- Acceptance:
  - project-level skills completeness becomes an explicit deliverable, not an accidental byproduct

4) Stage verification/audit expectations
- Deliverables:
  - define future tests/audits that verify:
    - skill index completeness
    - docs-to-skill routing coverage
    - generic LOOP skill availability once decoupling lands
- Acceptance:
  - the skills layer has a planned verification story rather than only manual review

## TDD / verification plan for later implementation
When implementation starts, add at least:
- checks for skill index completeness and routing coverage
- checks for generic-vs-adapter skill classification docs
- checks that library-facing docs/examples point to generic LOOP skills rather than only LeanAtlas-branded ones

Expected verification commands for the implementation wave:
- `uv run --locked python tests/contract/check_skills_standard_headers.py`
- `uv run --locked python tests/contract/check_loop_mainline_docs_integration.py`
- `uv run --locked python tests/contract/check_agents_navigation_coverage.py`
- `uv run --locked python tests/run.py --profile core`

## Decision log
- 2026-03-08: LOOP code/library decoupling is insufficient if skill routing remains LeanAtlas-only.
- 2026-03-08: LeanAtlas needs an explicit skill-governance/completeness rule for new capabilities; it cannot rely on ad hoc updates forever.
- 2026-03-08: current `leanatlas-loop-*` skills are acceptable for LeanAtlas mainline, but they must not be mistaken for a completed standalone LOOP skill layer.

## Rollback plan
- Remove this child plan and its corresponding master-plan bullet if the project decides not to pursue standalone LOOP skills or explicit project-level skills governance.

## Outcomes & retrospective (fill when done)
- Completed:
- Verification:
- Residual risks:
- Follow-on recommendation:
