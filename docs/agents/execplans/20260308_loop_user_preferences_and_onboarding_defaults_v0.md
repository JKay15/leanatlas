---
title: Stage user-configurable LOOP defaults and post-onboarding preference presets
owner: Codex (local workspace)
status: done
created: 2026-03-08
parent_execplan: docs/agents/execplans/20260307_loop_core_parallel_nested_batch_v0.md
---

## Purpose / Big Picture
LOOP now has enough committed mainline surface that users need a small number of explicit, stable operating presets. New users should not be forced to understand raw LOOP internals such as `assurance_level`, staged-review lineage, or provider-profile routing before they can use the system. At the same time, those defaults cannot stay hidden in chat-only conventions. This plan stages a bounded user-preference layer that sits after environment onboarding and before normal LOOP task execution.

The goal is not to expose every runtime knob. The goal is to expose only the few settings that materially affect user cost, latency, and closeout strictness, in names a new user can understand and reuse.

## Scope
In scope:
- define the user-facing preference layer for current LOOP mainline usage
- keep that layer preset-based rather than raw-parameter-based
- bind the preference layer to onboarding/mainline docs, skills, and later workflow integration
- define how defaults are stored, surfaced, and overridden by later runs

Out of scope:
- implementing a GUI or app-specific settings page in this planning wave
- exposing low-level timeout, semantic-idle, or reconciliation internals directly to new users
- forcing every current runtime path to honor the new preferences before the execution-layer work lands

## User-facing settings to stage
The preference layer should expose only these bounded items:

1) Default assurance preset
- `Balanced` (recommended)
- `Budget Saver`
- `Auditable`

2) Default agent provider
- example: `codex_cli`

3) Default FAST reviewer profile
- `low`
- `medium`

4) Whether large-scope review may automatically use pyramid review
- `enabled`
- `disabled`

These presets map to LOOP internals, but new users should not need to manipulate raw combinations like `FAST + medium + manual partition narrowing + custom followup ids`.

## Design constraints
- Preference selection should happen after environment onboarding, not during bootstrap consent.
- Preferences must be explicit and inspectable, not hidden in chat-only convention.
- Preferences must remain overridable per task/run.
- Presets must not misrepresent unimplemented behavior as already automatic.
- New users should see stable preset names and short consequences, not low-level LOOP jargon.

## Interfaces and Files
- `docs/agents/ONBOARDING.md`
- `docs/setup/QUICKSTART.md`
- `docs/agents/LOOP_MAINLINE.md`
- `docs/agents/MAINTAINER_WORKFLOW.md`
- `docs/agents/OPERATOR_WORKFLOW.md`
- `.agents/skills/leanatlas-onboard/SKILL.md`
- `.agents/skills/leanatlas-loop-mainline/SKILL.md`
- `.agents/skills/leanatlas-loop-review-acceleration/SKILL.md`
- `docs/contracts/LOOP_RUNTIME_CONTRACT.md`
- `docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md`
- `docs/contracts/LOOP_PYTHON_SDK_CONTRACT.md`
- future persisted preference artifact path (to be finalized during implementation)

## Milestones
1) Freeze the bounded preference surface
- Deliverables:
  - one authoritative list of user-facing LOOP preference presets and switches
  - explicit mapping from presets to current LOOP semantics
- Acceptance:
  - new users are not asked to configure low-level review/runtime parameters directly

2) Define preset semantics
- Deliverables:
  - `Balanced` maps to the recommended default development path
  - `Budget Saver` maps to the lowest-cost supported review/assurance path
  - `Auditable` maps to the publication-grade closeout path
  - explicit note that pyramid-review automation and staged execution may remain partial until corresponding execution work lands
- Acceptance:
  - no preset claims behavior that current mainline does not actually support

3) Stage preference storage and override rules
- Deliverables:
  - define where the preference artifact lives
  - define how later LOOP sessions read it
  - define how per-run overrides supersede stored defaults without mutating history
- Acceptance:
  - later runs can cite which defaults were active without relying on hidden chat state

4) Stage doc/skill integration
- Deliverables:
  - onboarding docs explain that LOOP preferences are post-onboarding defaults, not bootstrap blockers
  - mainline docs explain which current defaults are safe to choose
  - skills route users to presets instead of raw internal tuning
- Acceptance:
  - a new user can understand the few supported LOOP choices without learning contracts first

## TDD / verification plan for later implementation
When implementation starts, add at least:
- contract/doc checks proving the preference matrix and docs stay aligned
- deterministic tests for preset-to-runtime mapping
- workflow tests proving per-run override beats stored default without silent mutation

Expected verification commands for the implementation wave:
- `uv run --locked python tests/contract/check_loop_contract_docs.py`
- `uv run --locked python tests/contract/check_loop_python_sdk_contract_surface.py`
- `uv run --locked python tests/contract/check_loop_mainline_docs_integration.py`
- `uv run --locked python tests/contract/check_skills_standard_headers.py`
- `uv run --locked python tests/run.py --profile core`

## Decision log
- 2026-03-08: user-facing LOOP defaults must be preset-based, not raw-parameter-based.
- 2026-03-08: onboarding should prepare the environment first; LOOP operating preferences belong after onboarding, not inside bootstrap consent.
- 2026-03-08: exposing `FAST/LIGHT/STRICT`, pyramid review, and reviewer profile as raw orthogonal knobs would be too confusing for new users.

## Rollback plan
- Remove this child plan and delete the corresponding staged bullet from the master batch plan if the project decides not to expose user-facing LOOP defaults.

## Outcomes & retrospective (fill when done)
- Completed:
  - added committed `tools.loop.user_preferences` helpers for preset storage, loading, override resolution, and runtime mapping
  - staged post-onboarding preference artifact at `.cache/leanatlas/onboarding/loop_preferences.json`
  - routed onboarding/quickstart/mainline docs and LOOP skills through the bounded preset surface
  - kept the exposed user settings limited to assurance preset, provider, FAST reviewer profile, and large-scope pyramid-review toggle
- Verification:
  - `uv run --locked python tests/contract/check_loop_user_preferences_policy.py`
  - `uv run --locked python tests/contract/check_loop_contract_docs.py`
  - `uv run --locked python tests/contract/check_loop_python_sdk_contract_surface.py`
  - `uv run --locked python tests/contract/check_loop_mainline_docs_integration.py`
  - `uv run --locked python tests/contract/check_skills_standard_headers.py`
  - `uv run --locked python tests/run.py --profile core` (one profile run hit an existing `check_problem_state_reconcile.py` tmp-path race; isolated rerun passed)
  - `uv run --locked python tests/run.py --profile nightly` (one profile run hit an existing `check_scenario_tool_reuse_scoring.py` tmp-cleanup race; isolated rerun passed)
  - `lake build`
  - `git diff --check`
- Residual risks:
  - current preference handling stages explicit defaults and overrides, but not every runtime path consumes them yet
  - pyramid review remains a staged strategy surface; the default automated execution layer is still follow-on work
- Follow-on recommendation:
  - wire the stored preferences into the future default review-execution/orchestration path so users no longer need chat-level guidance to benefit from the presets
