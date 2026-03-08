---
title: Clarify external-paper ingress requirements for LeanAtlas onboarding and operator routing
status: done
created: 2026-03-08
owners:
  - codex
---

# Why

LeanAtlas currently assumes Codex is operating on repository-scoped assets. When a user points Codex at a LaTeX/PDF file outside the repository, LeanAtlas `AGENTS.md` and skills do not automatically attach to that external path. This behavior is mechanically correct for path-scoped instructions, but it is too easy for users to misinterpret as "LeanAtlas ignored its own workflow". We need explicit documentation that repository-external papers must first be ingressed into LeanAtlas scope before OPERATOR/formalization guidance is expected to apply.

# Scope

- document the repository-scope rule in root onboarding/operator entrypoints
- document the bounded ingress expectation for external papers
- update onboarding/operator skills so Codex can route correctly
- add doc-level guards to prevent this wording from drifting again

# Out of scope

- implementing a new external-ingress runtime
- changing OPERATOR patch boundaries
- adding new formalization automation

# Milestones

1. Freeze doc/test expectations for external-paper ingress wording.
2. Update root onboarding/operator entrypoints and related skills.
3. Regenerate file index, rerun targeted checks, and close out.

# Outcomes

- Clarified in `AGENTS.md` that LeanAtlas instructions are path-scoped and do not automatically govern repository-external paper sources.
- Updated `docs/agents/ONBOARDING.md` and `.agents/skills/leanatlas-onboard/SKILL.md` so post-onboarding guidance explicitly tells users to ingress external papers into LeanAtlas-controlled paths before expecting OPERATOR/formalization routing.
- Updated `docs/agents/OPERATOR_WORKFLOW.md` and `.agents/skills/leanatlas-operator-proof-loop/SKILL.md` with a hard ingress rule for repository-external LaTeX/PDF inputs.
- Added doc-level guards in:
  - `tests/contract/check_loop_mainline_docs_integration.py`
  - `tests/contract/check_setup_docs.py`
- Regenerated `docs/navigation/FILE_INDEX.md`.
- Verified with:
  - `uv run --locked python tests/contract/check_loop_mainline_docs_integration.py`
  - `uv run --locked python tests/contract/check_setup_docs.py`
  - `uv run --locked python tests/contract/check_skills_standard_headers.py`
  - `uv run --locked python tests/contract/check_file_index_reachability.py`
  - `git diff --check`
