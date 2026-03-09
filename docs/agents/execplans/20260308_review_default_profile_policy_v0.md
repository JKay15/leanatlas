---
title: Make FAST+low the default LOOP reviewer policy
owner: Codex (local workspace)
status: done
created: 2026-03-08
parent_execplan: docs/agents/execplans/20260307_loop_core_parallel_nested_batch_v0.md
---

## Purpose / Big Picture
Recent mainline dogfooding showed that `FAST + low` review closes real maintainer/documentation waves at a fraction of the token cost previously spent on `STRICT / xhigh`. The current mainline already exposes user preference presets and review-acceleration helpers, but the documented defaults still overstate `Balanced`/`STRICT` style paths as the general recommendation. This plan updates the committed default-review policy so that `FAST + low` is the baseline path, `medium` is a bounded opt-up for small-scope high-risk core logic, and `STRICT / xhigh` is reserved for rare cases that explicitly justify higher audit cost.

This is not a full review-orchestration execution change. The goal is to align default policy, preference storage defaults, onboarding/mainline docs, and helper semantics so later automation layers inherit the cheaper default instead of an older heavier recommendation.

## Glossary
- `FAST + low`: the default review path using FAST assurance expectations and a low-cost reviewer profile.
- `medium escalation`: a scoped opt-up used only for small-scope, high-risk core logic when FAST+low is not enough.
- `STRICT / xhigh`: the highest-cost closeout profile class, kept available but no longer treated as the normal default.
- `review policy defaults`: the committed preference/storage/doc defaults that later review runners and orchestrators should inherit unless a run overrides them.

## Scope
In scope:
- update committed LOOP preference defaults so the stored/default recommendation becomes `Budget Saver` + `low`
- update review-policy docs/contracts/skills so `FAST + low` is the explicit default
- add/update deterministic tests that lock the cheaper default policy
- keep pyramid review available, but document it as a strategy that may still escalate to `medium` only when risk/scope justify it

Out of scope:
- implementing full automated staged review execution
- removing `STRICT` or `xhigh` support from the system
- changing non-LOOP project review policies outside the documented LOOP default surfaces

## Interfaces and Files
- `docs/agents/execplans/20260307_loop_core_parallel_nested_batch_v0.md`
- `docs/agents/execplans/README.md`
- `docs/agents/execplans/20260308_review_default_profile_policy_v0.md`
- `tools/loop/user_preferences.py`
- `tools/loop/review_strategy.py`
- `docs/contracts/LOOP_PYTHON_SDK_CONTRACT.md`
- `docs/agents/ONBOARDING.md`
- `docs/setup/QUICKSTART.md`
- `docs/agents/LOOP_MAINLINE.md`
- `.agents/skills/leanatlas-onboard/SKILL.md`
- `.agents/skills/leanatlas-loop-mainline/SKILL.md`
- `.agents/skills/leanatlas-loop-review-acceleration/SKILL.md`
- `tests/contract/check_loop_user_preferences_policy.py`
- `tests/contract/check_loop_contract_docs.py`
- `tests/contract/check_loop_python_sdk_contract_surface.py`
- `tests/contract/check_loop_review_strategy.py`

## Milestones
1) Freeze the new default-review policy in tests
- Deliverables:
  - extend contract tests so they fail if the default preset stays `Balanced`
  - lock doc/skill wording that `FAST + low` is the default and `medium` is bounded escalation
- Commands:
  - `uv run --locked python tests/contract/check_loop_user_preferences_policy.py`
  - `uv run --locked python tests/contract/check_loop_review_strategy.py`
- Acceptance:
  - tests fail before implementation and describe the old default-policy mismatch

2) Implement default-policy surface changes
- Deliverables:
  - preference helpers default to `Budget Saver` + `low`
  - review-strategy helper surface exposes the committed default policy for future consumers
  - contracts/docs explain `medium` escalation and demote `STRICT / xhigh` to exceptional use
- Commands:
  - `uv run --locked python tests/contract/check_loop_user_preferences_policy.py`
  - `uv run --locked python tests/contract/check_loop_contract_docs.py`
  - `uv run --locked python tests/contract/check_loop_python_sdk_contract_surface.py`
  - `uv run --locked python tests/contract/check_loop_review_strategy.py`
- Acceptance:
  - docs/contracts/tests agree on the cheaper default
  - no code path claims `STRICT / xhigh` is the recommended baseline

3) Integrate onboarding/mainline/skills wording
- Deliverables:
  - onboarding/mainline/quickstart describe `FAST + low` as the default
  - skills mirror the same default-policy guidance
  - master plan/execplan index mention the new child plan
- Commands:
  - `uv run --locked python tests/contract/check_loop_user_preferences_policy.py`
  - `uv run --locked python tests/contract/check_skills_standard_headers.py`
  - `uv run --locked python tests/contract/check_file_index_reachability.py`
- Acceptance:
  - a new user reading the mainline path sees the cheaper default first
  - skills no longer imply `Balanced`/`STRICT` is the standard path

4) Verify and close through maintainer LOOP
- Deliverables:
  - verify note
  - FAST review artifacts
  - settled maintainer closeout ref
- Commands:
  - `uv run --locked python tests/run.py --profile core`
  - `lake build`
  - `git diff --check`
- Acceptance:
  - maintainer session closes `PASSED`
  - final closeout cites fresh FAST review evidence

## Testing plan (TDD)
- Extend `tests/contract/check_loop_user_preferences_policy.py` to require:
  - default stored preset = `Budget Saver`
  - default runtime assurance = `FAST`
  - `low` remains the default reviewer profile
  - docs/skills name `FAST + low` as the default
- Extend `tests/contract/check_loop_review_strategy.py` to lock any new default-policy helper or constants that expose the recommended staged profile policy
- Re-run:
  - `uv run --locked python tests/contract/check_loop_contract_docs.py`
  - `uv run --locked python tests/contract/check_loop_python_sdk_contract_surface.py`
  - `uv run --locked python tests/contract/check_skills_standard_headers.py`
  - `uv run --locked python tests/run.py --profile core`
  - `lake build`

## Decision log
- 2026-03-08: `FAST + low` becomes the committed default reviewer policy because recent mainline waves closed successfully at much lower token cost.
- 2026-03-08: `medium` stays available, but only as a bounded escalation for small-scope, high-risk core logic.
- 2026-03-08: `STRICT / xhigh` remains supported for exceptional audit-heavy cases and is no longer documented as the normal default.

## Rollback plan
- Revert the new child plan and restore the previous default preset/profile wording if the cheaper default proves to miss important findings in later dogfooding.
- Verify rollback by re-running:
  - `uv run --locked python tests/contract/check_loop_user_preferences_policy.py`
  - `uv run --locked python tests/contract/check_loop_review_strategy.py`

## Outcomes & retrospective (fill when done)
- Completed: committed LOOP default-review policy now prefers `Budget Saver` + `FAST + low`, exposes a machine-readable `build_default_review_policy()` helper, and documents `medium` as a bounded opt-up only for small-scope high-risk core logic.
- Completed: onboarding, quickstart, LOOP mainline docs, and the relevant LOOP skills now present `FAST + low` as the default path instead of implying `Balanced`/`STRICT` as the normal recommendation.
- Completed: contract and policy tests now lock the cheaper default and reject regressions that would silently move the baseline back toward heavier reviewer profiles.
- Verification: targeted contract checks, `python tests/run.py --profile core`, `python tests/run.py --profile nightly`, `lake build`, and `git diff --check` passed for the final working tree.
- FAST review closeout: final closeout will cite a fresh FAST review for the settled default-policy surface, preserving the low-cost default dogfooding discipline that motivated this change.
