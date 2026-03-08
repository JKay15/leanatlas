---
title: Surface reviewer exhaustiveness protocol in onboarding
status: done
created: 2026-03-08
owners:
  - codex
---

# Why

`tools/loop/review_prompting.py` and the exhaustive reviewer protocol are now committed mainline capabilities, but they are still too easy to miss from the first-run path. New threads can find them by search, yet onboarding does not explicitly route Codex to the feature, so the capability is not reliably discoverable.

# Scope

- add a doc/test guard that onboarding surfaces mention the exhaustive reviewer protocol
- update `docs/agents/ONBOARDING.md`
- update `.agents/skills/leanatlas-onboard/SKILL.md`
- keep scope bounded to onboarding discoverability only

# Out of scope

- changing default reviewer policy again
- adding a new standalone skill
- changing repair-wave/runtime behavior

# Milestones

1. Freeze discoverability requirement in tests.
2. Update onboarding doc and onboarding skill.
3. Re-run targeted checks and close out.

# Outcomes

- Added a doc/test guard in `tests/contract/check_loop_mainline_docs_integration.py` that requires onboarding docs and the onboarding skill to surface reviewer exhaustiveness, `review.prompt.exhaustive.v1`, and `tools/loop/review_prompting.py`.
- Updated `docs/agents/ONBOARDING.md` so post-onboarding LOOP guidance explicitly routes users to the exhaustive reviewer protocol and `docs/agents/LOOP_MAINLINE.md`.
- Updated `.agents/skills/leanatlas-onboard/SKILL.md` so first-run routing now advertises the same reviewer-exhaustiveness path instead of leaving it buried in contracts/execplans.
- Verified with:
  - `uv run --locked python tests/contract/check_loop_mainline_docs_integration.py`
  - `uv run --locked python tests/contract/check_loop_user_preferences_policy.py`
  - `uv run --locked python tests/contract/check_onboarding_automation_gate.py`
  - `uv run --locked python tests/contract/check_onboarding_banner_locale_contract.py`
  - `uv run --locked python tests/contract/check_skills_standard_headers.py`
  - `git diff --check`
