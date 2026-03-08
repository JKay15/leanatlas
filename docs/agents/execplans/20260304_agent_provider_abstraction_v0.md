---
title: Agent provider abstraction v0 (Codex/Claude compatible runner interface)
owner: Codex (local workspace)
status: done
created: 2026-03-04
---

## Purpose / Big Picture
LeanAtlas currently relies on direct `--agent-cmd` strings and several Codex-specific defaults. This makes platform switching harder as the project grows. The goal of this plan is to add a minimal provider abstraction layer that keeps current behavior intact while enabling explicit provider selection (for example `codex_cli` or `claude_code`) and profile-based command resolution. The first version is intentionally small: no workflow redesign, no breaking changes, and no change to artifact schemas unrelated to agent execution. After this work, runners should accept either legacy `--agent-cmd` or provider/profile inputs and record deterministic invocation metadata.

## Glossary
- Agent provider: named execution backend (example: `codex_cli`, `claude_code`) mapped to a shell command template.
- Agent profile: JSON config file defining provider id, shell command, and optional env passthrough map.
- Resolved command: final shell command used by runner after combining CLI inputs + optional profile.
- Legacy mode: current behavior using `--agent-cmd` directly.

## Scope
In scope:
- `tools/agent_eval/run_pack.py`, `tools/agent_eval/run_scenario.py` CLI extension (`--agent-provider`, `--agent-profile`) with backward compatibility.
- New resolver utility for provider/profile resolution.
- Agent profile schema and a dummy profile fixture for tests.
- Contract/docs updates for new CLI behavior.
- Test updates (TDD-first) in existing registered tests.

Out of scope:
- Changing grading logic or scenario semantics.
- Removing `--agent-cmd`.
- Reworking automation/governor contracts beyond docs mention.

Allowed directories to change:
- `tools/**`
- `tests/**`
- `docs/contracts/**`
- `docs/schemas/**`
- `docs/agents/**` (this ExecPlan file only)

Forbidden:
- `LeanAtlas/**` proof libraries
- production problem files under `Problems/**`

## Interfaces and Files
- New utility: `tools/agent_eval/agent_provider.py`
  - resolves final shell command from:
    - `--agent-cmd` (legacy direct)
    - or `--agent-provider` (+ optional `--agent-profile`)
- New schema: `docs/schemas/AgentProfile.schema.json`
- New test profile fixture: `tests/agent_eval/profiles/dummy_agent.profile.json`
- Updated runners:
  - `tools/agent_eval/run_pack.py`
  - `tools/agent_eval/run_scenario.py`
- Updated contracts:
  - `docs/contracts/AGENT_EVAL_CONTRACT.md`
  - `docs/contracts/AGENT_EVAL_SCENARIO_CONTRACT.md`

## Milestones
1) TDD updates first
- Deliverables:
  - update existing core dummy e2e tests to exercise `--agent-profile` path
  - keep at least one legacy `--agent-cmd` path tested
- Commands:
  - `uv run --locked python tests/agent_eval/check_pack_runner_and_grader_with_dummy_agent.py`
  - `uv run --locked python tests/agent_eval/check_scenario_runner_and_grader_with_dummy_agent.py`
- Acceptance:
  - both tests fail before implementation, then pass after implementation

2) Implement provider/profile resolver
- Deliverables:
  - add `tools/agent_eval/agent_provider.py`
  - add `docs/schemas/AgentProfile.schema.json`
  - add `tests/agent_eval/profiles/dummy_agent.profile.json`
- Commands:
  - targeted test commands above
- Acceptance:
  - runner can resolve and execute via profile without explicit `--agent-cmd`

3) Integrate runners with backward compatibility
- Deliverables:
  - modify `run_pack.py` and `run_scenario.py`
  - record resolved invocation metadata into run artifacts
- Commands:
  - same targeted tests
  - `uv run --locked python tests/agent_eval/check_runner_plan_mode.py`
  - `uv run --locked python tests/agent_eval/check_scenario_runner_plan_mode.py`
- Acceptance:
  - legacy and provider/profile flows both work in smoke paths

4) Contract/doc updates + core verification
- Deliverables:
  - update contract docs with new CLI options and compatibility notes
- Commands:
  - `uv run --locked python tests/run.py --profile core`
- Acceptance:
  - core profile passes

## Testing plan (TDD)
- Modify registered tests first:
  - `tests/agent_eval/check_pack_runner_and_grader_with_dummy_agent.py`
  - `tests/agent_eval/check_scenario_runner_and_grader_with_dummy_agent.py`
- Coverage:
  - profile-based run path
  - unchanged deterministic grading path
  - CLI parse compatibility in plan smoke tests
- Contamination control:
  - all test outputs remain under temporary dirs / existing artifacts roots used by tests
  - no new persistent runtime side effects required

## Decision log
- Chosen minimal abstraction (provider/profile resolver) instead of full runtime subsystem migration to reduce risk and keep backward compatibility.
- Chosen profile fixture JSON (not YAML) to align with existing schema validation stack (`jsonschema`).
- Chosen to update existing registered tests first, avoiding manifest expansion in this patch.

## Rollback plan
- Revert these files if regressions appear:
  - `tools/agent_eval/agent_provider.py`
  - `tools/agent_eval/run_pack.py`
  - `tools/agent_eval/run_scenario.py`
  - `docs/schemas/AgentProfile.schema.json`
  - updated test files and docs
- Verify rollback by rerunning:
  - `uv run --locked python tests/agent_eval/check_pack_runner_and_grader_with_dummy_agent.py`
  - `uv run --locked python tests/agent_eval/check_scenario_runner_and_grader_with_dummy_agent.py`

## Outcomes & retrospective (fill when done)
- Completed:
  - Added provider/profile resolver: `tools/agent_eval/agent_provider.py`.
  - Added profile schema: `docs/schemas/AgentProfile.schema.json`.
  - Added test profile fixture: `tests/agent_eval/profiles/dummy_agent.profile.json`.
  - Integrated both runners:
    - `tools/agent_eval/run_pack.py`
    - `tools/agent_eval/run_scenario.py`
  - Added audit metadata emission per run step/run variant:
    - `agent_invocation.json` (provider/source/profile_path hash metadata).
  - Updated contracts:
    - `docs/contracts/AGENT_EVAL_CONTRACT.md`
    - `docs/contracts/AGENT_EVAL_SCENARIO_CONTRACT.md`
  - Updated deterministic inventory doc:
    - `docs/setup/TEST_ENV_INVENTORY.md`

- Verification run:
  - Red->Green TDD:
    - `uv run --locked python tests/agent_eval/check_pack_runner_and_grader_with_dummy_agent.py` (failed before implementation, passes after)
    - `uv run --locked python tests/agent_eval/check_scenario_runner_and_grader_with_dummy_agent.py` (failed before implementation, passes after)
  - Additional targeted:
    - `uv run --locked python tests/agent_eval/check_runner_plan_mode.py`
    - `uv run --locked python tests/agent_eval/check_scenario_runner_plan_mode.py`
    - `uv run --locked python tests/schema/validate_schemas.py`
  - Full core:
    - `uv run --locked python tests/run.py --profile core` (PASS)

- Notes:
  - Legacy `--agent-cmd` is preserved.
  - New interface is additive: users can migrate incrementally to `--agent-profile` / `--agent-provider`.
