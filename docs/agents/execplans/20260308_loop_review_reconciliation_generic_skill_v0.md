---
title: Add generic LOOP review reconciliation skill and LeanAtlas adapter routing
owner: Codex (local workspace)
status: done
created: 2026-03-08
parent_execplan: docs/agents/execplans/20260308_loop_skills_decoupling_and_project_skills_governance_v0.md
---

## Purpose / Big Picture
`review supersession / reconciliation runtime` is already implemented in mainline LOOP, but discoverability still depends on LeanAtlas-branded maintainer skills. That is the wrong boundary: this capability belongs to `LOOP core` and should have a reusable generic skill entry, while LeanAtlas-specific skills should only explain repository-local routing and verification.

This wave lands the first concrete slice of the broader skills-decoupling plan:
- add a generic `loop-review-reconciliation` skill
- route LOOP mainline docs/skills through it
- keep LeanAtlas maintainer skill as a thin adapter for repo-specific checks

## Scope
In scope:
- add a generic skill under `.agents/skills/loop-review-reconciliation/SKILL.md`
- wire `.agents/skills/README.md`, `docs/agents/README.md`, and `docs/agents/LOOP_MAINLINE.md`
- update LeanAtlas LOOP skills so reconciliation-specific tasks route through the generic skill
- add deterministic contract coverage for the new routing

Out of scope:
- broader LOOP library extraction/packaging
- full generic skill split for every existing `leanatlas-loop-*` skill
- repair-wave logic or runtime behavior changes

## Interfaces and Files
- `.agents/skills/loop-review-reconciliation/SKILL.md`
- `.agents/skills/README.md`
- `.agents/skills/leanatlas-loop-mainline/SKILL.md`
- `.agents/skills/leanatlas-loop-maintainer-ops/SKILL.md`
- `docs/agents/README.md`
- `docs/agents/LOOP_MAINLINE.md`
- `tests/contract/check_loop_review_reconciliation_skill_integration.py`
- `tests/manifest.json`
- `docs/testing/TEST_MATRIX.md`
- `docs/navigation/FILE_INDEX.md`

## Milestones
1) Freeze the generic skill surface
- Deliverables:
  - one generic skill for review reconciliation with standard headers and role-neutral wording
- Acceptance:
  - the skill explains `CONFIRMED | DISMISSED | SUPERSEDED`, `finding_key`, `finding_group_key`, and `scope_lineage_key`
  - the skill does not depend on LeanAtlas role names for its core explanation

2) Wire LeanAtlas routing to the generic skill
- Deliverables:
  - mainline doc and skill index reference the generic skill
  - LeanAtlas LOOP skills route reconciliation-specific tasks into the generic skill
- Acceptance:
  - a maintainer can discover reconciliation runtime from docs/skills without relying on chat context

3) Add deterministic contract coverage
- Deliverables:
  - a contract test that proves the generic skill exists and is reachable from mainline routing docs/skills
- Acceptance:
  - failing any one of the above routes breaks the test

## TDD plan
1. Add `tests/contract/check_loop_review_reconciliation_skill_integration.py`
2. Register it in `tests/manifest.json`
3. Regenerate `docs/testing/TEST_MATRIX.md`
4. Implement doc/skill wiring until the new test passes
5. Regenerate `docs/navigation/FILE_INDEX.md`

## Verification
- `uv run --locked python tests/contract/check_loop_review_reconciliation_skill_integration.py`
- `uv run --locked python tests/contract/check_skills_standard_headers.py`
- `uv run --locked python tests/contract/check_loop_mainline_docs_integration.py`
- `uv run --locked python tests/run.py --profile core`
- `uv run --locked python tests/run.py --profile nightly`
- `lake build`
- `git diff --check`

## Decision log
- 2026-03-08: this slice intentionally avoids runtime changes so it stays low-conflict with the pending xhigh repair wave.
- 2026-03-08: the first decoupled skill should target a capability already fully implemented in LOOP core.
- 2026-03-08: nested skills must be committed before this slice is considered complete; otherwise clean checkouts would still miss the new generic skill.
- 2026-03-08: fresh `medium` review in the shared dirty tree bled into unrelated repair-wave diffs, so closeout for this slice falls back to explicit tooling triage evidence rather than pretending to have a clean in-scope review.

## Outcomes & retrospective (fill when done)
- Completed:
  - added generic `.agents/skills/loop-review-reconciliation/SKILL.md`
  - routed LeanAtlas mainline and maintainer docs/skills through the generic reconciliation skill
  - added deterministic contract coverage for discoverability and routing
  - committed the nested skills repo so root gitlink can point at a clean-checkout-compatible skill revision
- Verification:
  - `uv run --locked python tests/contract/check_loop_review_reconciliation_skill_integration.py`
  - `uv run --locked python tests/contract/check_skills_standard_headers.py`
  - `uv run --locked python tests/contract/check_loop_mainline_docs_integration.py`
  - `uv run --locked python tests/contract/check_agents_navigation_coverage.py`
  - `uv run --locked python tests/contract/check_file_index_reachability.py`
  - `uv run --locked python tests/contract/check_test_matrix_up_to_date.py`
  - `uv run --locked python tests/contract/check_manifest_completeness.py`
  - `lake build`
  - `git diff --check`
- Residual risks:
  - fresh AI review for this slice in the shared working tree observed unrelated repair-wave diffs, so the review evidence is only suitable for tooling-triage closeout
  - fresh `core`/`nightly` reruns for this slice remain blocked by unrelated concurrent repair-wave edits outside scope
- Follow-on recommendation:
  - once the repair wave lands or moves to an isolated worktree, rerun a clean scoped AI review and full `core`/`nightly` verify to upgrade this slice from targeted verification to full branch-level verification
