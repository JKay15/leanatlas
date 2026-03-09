---
title: Promote low+medium to the committed default LOOP reviewer tier policy
owner: Codex (local workspace)
status: done
created: 2026-03-08
parent_execplan: docs/agents/execplans/20260307_loop_core_parallel_nested_batch_v0.md
---

## Purpose / Big Picture
Recent mainline dogfooding established two things at once: `FAST + low` remains the right cheap baseline, and `pure medium` can close a small-scope high-risk core feature with materially better signal than `low` without reopening `STRICT / xhigh` as the default. The current mainline already documents `medium` as a bounded escalation, but that policy still mostly lives as prose. This plan promotes the policy into a committed tiered default surface: low is the default baseline, medium is the normal escalation tier for small-scope high-risk core logic, and `STRICT / xhigh` is reserved for explicit exceptions.

This is not the full automated review-orchestration wave. The goal here is to make the default policy machine-readable and consistent across preference helpers, strategy helpers, contracts, onboarding/mainline docs, and skills so later automation layers inherit the new tiered default without ambiguity.

## Glossary
- `tiered reviewer policy`: the committed default profile/escalation policy for maintainer LOOP review.
- `LOW_PLUS_MEDIUM`: low is the baseline tier; medium is the standard escalation tier before any `STRICT / xhigh` exception.
- `baseline tier`: the cheapest normal reviewer path (`FAST + low`).
- `exception tier`: the rare `STRICT / xhigh` path used only when audit strength explicitly justifies it.

## Scope
In scope:
- promote a machine-readable `LOW_PLUS_MEDIUM` default policy into LOOP preference and strategy helpers
- preserve `Budget Saver` + `FAST` as the baseline preset/assurance default
- update contracts/docs/skills so they describe the same tiered default
- add deterministic tests that fail if mainline drifts back to “pure low only” or re-elevates `STRICT / xhigh` as the normal path

Out of scope:
- full automated staged review execution
- changing the review runner to always auto-escalate without orchestration logic
- removing user ability to force `medium` or explicit exception paths

## Interfaces and Files
- `docs/agents/execplans/20260307_loop_core_parallel_nested_batch_v0.md`
- `docs/agents/execplans/README.md`
- `docs/agents/execplans/20260308_review_tiered_default_policy_v0.md`
- `tools/loop/user_preferences.py`
- `tools/loop/review_strategy.py`
- `tools/loop/__init__.py`
- `docs/contracts/LOOP_PYTHON_SDK_CONTRACT.md`
- `docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md`
- `docs/agents/LOOP_MAINLINE.md`
- `docs/agents/ONBOARDING.md`
- `docs/setup/QUICKSTART.md`
- `.agents/skills/leanatlas-onboard/SKILL.md`
- `.agents/skills/leanatlas-loop-mainline/SKILL.md`
- `.agents/skills/leanatlas-loop-review-acceleration/SKILL.md`
- `tests/contract/check_loop_user_preferences_policy.py`
- `tests/contract/check_loop_review_strategy.py`
- `tests/contract/check_loop_contract_docs.py`
- `tests/contract/check_loop_python_sdk_contract_surface.py`

## Milestones
1) Freeze the tiered default in tests
- Deliverables:
  - extend preference/strategy tests so they require a machine-readable `LOW_PLUS_MEDIUM` default
  - require docs/contracts to say low is the baseline and medium is the standard bounded escalation tier
- Commands:
  - `uv run --locked python tests/contract/check_loop_user_preferences_policy.py`
  - `uv run --locked python tests/contract/check_loop_review_strategy.py`
- Acceptance:
  - tests fail before implementation and describe the current “pure low default” gap

2) Implement tiered default helper surfaces
- Deliverables:
  - preference helpers expose and persist the default tiered reviewer policy
  - strategy helpers expose a canonical default tiered-review policy object for future automation
  - mainline exports expose the new helper surface
- Commands:
  - `uv run --locked python tests/contract/check_loop_user_preferences_policy.py`
  - `uv run --locked python tests/contract/check_loop_review_strategy.py`
- Acceptance:
  - machine-readable helper surfaces agree on `LOW_PLUS_MEDIUM`

3) Align contracts, onboarding, mainline docs, and skills
- Deliverables:
  - SDK/wave contracts describe the tiered default accurately
  - onboarding/mainline/quickstart route users through low baseline + medium escalation
  - relevant LOOP skills mirror the same default
- Commands:
  - `uv run --locked python tests/contract/check_loop_contract_docs.py`
  - `uv run --locked python tests/contract/check_loop_python_sdk_contract_surface.py`
  - `uv run --locked python tests/contract/check_skills_standard_headers.py`
- Acceptance:
  - no authoritative doc still implies “pure low only” is the complete default story
  - no authoritative doc treats `STRICT / xhigh` as a standard default

4) Verify and close through maintainer LOOP
- Deliverables:
  - verify note
  - final AI review evidence
  - settled maintainer LOOP closeout
- Commands:
  - `uv run --locked python tests/run.py --profile core`
  - `uv run --locked python tests/run.py --profile nightly`
  - `lake build`
  - `git diff --check`
- Acceptance:
  - final working tree closes `PASSED`
  - final closeout cites fresh review evidence from the final tiered-policy state

## Testing plan (TDD)
- Extend `tests/contract/check_loop_user_preferences_policy.py` to require:
  - `DEFAULT_REVIEW_TIER_POLICY = LOW_PLUS_MEDIUM`
  - stored preference defaults preserve that policy
  - effective runtime exports the tiered policy
- Extend `tests/contract/check_loop_review_strategy.py` to require a canonical machine-readable tiered-review helper for future orchestration
- Re-run:
  - `uv run --locked python tests/contract/check_loop_contract_docs.py`
  - `uv run --locked python tests/contract/check_loop_python_sdk_contract_surface.py`
  - `uv run --locked python tests/contract/check_skills_standard_headers.py`
  - `uv run --locked python tests/run.py --profile core`
  - `uv run --locked python tests/run.py --profile nightly`
  - `lake build`

## Decision log
- 2026-03-08: keep `Budget Saver` + `FAST` as the baseline preset/assurance default.
- 2026-03-08: promote `LOW_PLUS_MEDIUM` to the committed default reviewer tier policy.
- 2026-03-08: keep `STRICT / xhigh` available only for explicit exception cases rather than a normal default.

## Rollback plan
- revert the tiered-policy helper, docs, and tests
- keep the historical medium-trial evidence so future policy work still has an audit trail

## Outcomes & retrospective (fill when done)
- Completed.
- The committed default reviewer tier policy is now machine-readable rather than prose-only:
  - baseline remains `FAST + low`
  - bounded escalation tier is `medium`
  - explicit `STRICT / xhigh` closeout remains available only as an exception path
- Preference helpers, strategy helpers, orchestration helpers, contracts, onboarding/mainline docs, and LOOP skills now describe the same low+medium default.
- Replay validation was hardened across the implementation wave:
  - `strategy_plan.bounded_medium_profile` is authoritative provenance and `MEDIUM` final closeout must match it exactly
  - `strategy_plan.strict_exception_profile` is authoritative provenance and `STRICT` final closeout must match it exactly
- The implementation wave surfaced and fixed several real regressions via pure medium review, including:
  - broken strategy-fingerprint placement
  - missing strict exception path
  - replay holes that allowed lower-tier or arbitrary profiles to masquerade as `STRICT` or `MEDIUM` final closeout profiles
- Final verification passed on the settled implementation state and a fresh medium review closed clean with `No findings.`:
  - prompt: [20260308_review_tiered_default_policy_review_round7_medium_prompt.md](/Users/xiongjiangkai/xjk_papers/leanatlas/artifacts/reviews/20260308_review_tiered_default_policy_review_round7_medium_prompt.md)
  - response: [20260308_review_tiered_default_policy_review_round8_medium_response.md](/Users/xiongjiangkai/xjk_papers/leanatlas/artifacts/reviews/20260308_review_tiered_default_policy_review_round8_medium_response.md)
  - verify note: [20260308_review_tiered_default_policy_verify_round1.md](/Users/xiongjiangkai/xjk_papers/leanatlas/artifacts/verify/20260308_review_tiered_default_policy_verify_round1.md)
