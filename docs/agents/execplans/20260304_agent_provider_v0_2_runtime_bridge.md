---
title: Agent provider v0.2 (prompt transport + env map + automation bridge)
owner: Codex (local workspace)
status: done
created: 2026-03-04
---

## Purpose / Big Picture
v0 introduced provider/profile selection for Phase6 runners. v0.2 extends the interface so it can support more providers (including Claude Code) with fewer call-site assumptions. We add profile-level prompt transport and env mapping semantics, and we reuse the same resolver for automation advisor execution paths. This keeps call-sites stable while allowing provider migration through config rather than code edits.

## Glossary
- Prompt transport: how prompt/context is passed to agent (`stdin`, `env_path`, `arg`).
- Env map: profile-level mapping from source environment variable names to target variable names.
- Automation bridge: using the same provider/profile resolver in `run_automation.py` advisor execution.

## Scope
In scope:
- Extend `AgentProfile` schema with v0.2 optional fields:
  - `prompt_transport`, `prompt_arg`, `env_map`, `capabilities`.
- Extend resolver to normalize/emit these fields and apply env mapping.
- Add runner env harmonization for provider defaults.
- Extend automation wrapper/runner CLI with provider/profile flags and route advisor execution through resolver.
- Update relevant docs/contracts/tests.

Out of scope:
- Replacing automation handoff model in Codex App.
- Provider-specific deep adapters (no SDK integration).

## Interfaces and Files
- `tools/agent_eval/agent_provider.py`
- `docs/schemas/AgentProfile.schema.json`
- `tools/agent_eval/run_pack.py`
- `tools/agent_eval/run_scenario.py`
- `tools/coordination/run_automation.py`
- `tools/coordination/run_automation_local.py`
- `tests/agent_eval/profiles/dummy_agent.profile.json`
- `tests/automation/check_run_automation_local.py`
- `docs/contracts/AGENT_EVAL_CONTRACT.md`
- `docs/contracts/AGENT_EVAL_SCENARIO_CONTRACT.md`
- `docs/contracts/AUTOMATION_CONTRACT.md`

## Milestones
1) TDD first
- Update tests to require:
  - profile fixture with v0.2 fields
  - automation local wrapper forwarding provider/profile flags
- Run affected tests and capture initial failures.

2) Implement resolver v0.2
- Add schema fields + resolver support.
- Keep v0 behavior backward compatible.

3) Integrate automation bridge
- Add provider/profile options to `run_automation*`.
- Resolve advisor command from provider/profile when direct `exec_cmd` absent.

4) Verify + docs
- Update contracts.
- Run targeted tests and `core`.

## Testing plan (TDD)
- `uv run --locked python tests/agent_eval/check_pack_runner_and_grader_with_dummy_agent.py`
- `uv run --locked python tests/agent_eval/check_scenario_runner_and_grader_with_dummy_agent.py`
- `uv run --locked python tests/automation/check_run_automation_local.py`
- `uv run --locked python tests/run.py --profile core`

## Decision log
- Keep profile as JSON to align with current schema stack.
- Keep legacy `--agent-cmd` highest priority for explicit overrides.
- Keep automation handoff unchanged; bridge only affects optional local advisor execution.

## Rollback plan
- Revert the files listed in scope.
- Re-run targeted tests above to confirm pre-v0.2 behavior.

## Outcomes & retrospective (fill when done)
- Completed:
  - Extended `AgentProfile` schema with optional v0.2 fields:
    - `prompt_transport`, `prompt_arg`, `env_map`, `capabilities`.
  - Extended resolver:
    - `tools/agent_eval/agent_provider.py`
    - normalized/serialized v0.2 invocation metadata
    - added profile env remap helper (`apply_env_map`).
  - Integrated v0.2 metadata + env remap into runners:
    - `tools/agent_eval/run_pack.py`
    - `tools/agent_eval/run_scenario.py`.
  - Bridged automation advisor execution onto the same resolver path:
    - `tools/coordination/run_automation.py`
    - `tools/coordination/run_automation_local.py`
    - added `--agent-provider` and `--agent-profile` forwarding.
  - Extended automation registry schema + validator for advisor provider/profile fields.
  - Updated contract docs:
    - `docs/contracts/AGENT_EVAL_CONTRACT.md`
    - `docs/contracts/AGENT_EVAL_SCENARIO_CONTRACT.md`
    - `docs/contracts/AUTOMATION_CONTRACT.md`.

- Verification:
  - Targeted:
    - `uv run --locked python tests/agent_eval/check_pack_runner_and_grader_with_dummy_agent.py` (PASS)
    - `uv run --locked python tests/agent_eval/check_scenario_runner_and_grader_with_dummy_agent.py` (PASS)
    - `uv run --locked python tests/automation/check_run_automation_local.py` (PASS)
    - `uv run --locked python tests/agent_eval/check_runner_plan_mode.py` (PASS)
    - `uv run --locked python tests/agent_eval/check_scenario_runner_plan_mode.py` (PASS)
    - `uv run --locked python tests/automation/validate_registry.py` (PASS)
    - `uv run --locked python tests/schema/validate_schemas.py` (PASS)
    - `uv run --locked python tests/determinism/check_canonical_json.py` (PASS)
    - `uv run --locked python tests/contract/check_test_env_inventory_up_to_date.py` (PASS)
  - Full profile:
    - `uv run --locked python tests/run.py --profile core` (PASS)

- Notes:
  - Backward compatibility preserved: legacy `--agent-cmd` remains highest-priority explicit override.
  - v0.2 behavior is additive and config-driven; call-site migration to non-Codex providers can proceed incrementally.
