---
title: Wave isolated-review workspace hang recovery hardening
owner: codex
status: done
created: 2026-03-05
---

## Purpose / Big Picture
A Wave run currently can stall when the independent reviewer tool hangs in an isolated review workspace. When that happens, the second review round may never emit its response artifact, which can block LOOP completion even if implementation and deterministic checks are correct. This plan hardens subprocess execution so reviewer invocations always converge (success or timeout), with deterministic evidence for timeout outcomes. The outcome must prevent infinite waiting and preserve auditable traces required by STRICT mode.

## Glossary
- Isolated review workspace: temporary workspace used only for independent AI review.
- Hard timeout: absolute wall-clock timeout for one external command.
- Idle timeout: max silence window (stdout/stderr unchanged) before we terminate as stalled.
- Process-group kill: terminate the command and all children created in the same session.

## Scope
In scope:
- `tools/workflow/run_cmd.py` timeout/kill semantics.
- Agent invocation call sites that run reviewer-like commands (`tools/agent_eval/run_pack.py`, `tools/agent_eval/run_scenario.py`, `tools/coordination/run_automation.py`).
- New contract/runtime tests for timeout convergence.
- Wave execution contract doc updates for bounded reviewer execution.

Out of scope:
- redesigning LOOP state machine enums/reason codes.
- replacing external agent providers.

## Interfaces and Files
- `tools/workflow/run_cmd.py`
  - add `idle_timeout_s` argument.
  - enforce process-group termination on timeout.
- `tools/agent_eval/run_pack.py`
- `tools/agent_eval/run_scenario.py`
- `tools/coordination/run_automation.py`
  - pass idle-timeout defaults for agent/reviewer execution paths.
- `tests/contract/check_run_cmd_timeout_hardening.py` (new)
- `tests/manifest.json`, `docs/testing/TEST_MATRIX.md`
- `docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md`
- `tests/contract/check_loop_contract_docs.py`

## Milestones
1) Red tests first
- Deliverables:
  - add `tests/contract/check_run_cmd_timeout_hardening.py` with failing assertions against current behavior.
- Commands:
  - `uv run --locked python tests/contract/check_run_cmd_timeout_hardening.py`
- Acceptance:
  - fails before implementation.

2) Implement timeout hardening
- Deliverables:
  - update `tools/workflow/run_cmd.py` to support hard timeout + idle timeout + process-group cleanup.
- Commands:
  - `uv run --locked python tests/contract/check_run_cmd_timeout_hardening.py`
- Acceptance:
  - new test passes and leaves no orphan child process.

3) Wire reviewer-risk call sites
- Deliverables:
  - idle timeout wired in agent/reviewer execution calls.
- Commands:
  - `uv run --locked python tests/agent_eval/check_pack_runner_and_grader_with_dummy_agent.py`
  - `uv run --locked python tests/agent_eval/check_scenario_runner_and_grader_with_dummy_agent.py`
  - `uv run --locked python tests/automation/check_run_automation_local.py`
- Acceptance:
  - existing behavior stays green.

4) Contract + registry/doc sync
- Deliverables:
  - contract text for bounded reviewer execution and timeout evidence.
  - doc-snippet checker update.
  - register new test in manifest and regenerate matrix.
- Commands:
  - `uv run --locked python tests/contract/check_loop_contract_docs.py`
  - `uv run --locked python tools/tests/generate_test_matrix.py --write`
  - `uv run --locked python tests/contract/check_test_matrix_up_to_date.py`
- Acceptance:
  - contract check and matrix up-to-date check pass.

5) Full verification
- Commands:
  - `uv run --locked python tests/run.py --profile core`
  - `uv run --locked python tests/run.py --profile nightly`
  - `lake build`
- Acceptance:
  - all pass.

## Testing plan (TDD)
- New regression scenarios:
  - hard timeout must kill spawned child process tree.
  - idle timeout must terminate silent long-running command.
- Existing smoke/e2e coverage used to guard behavior regressions in pack/scenario/automation paths.

## Decision log
- 2026-03-05: choose process-group termination over parent-only kill to avoid orphan reviewer processes in isolated workspaces.
- 2026-03-05: keep existing span schema stable (`timed_out=true`, `exit_code=124`) to avoid report-schema churn.

## Rollback plan
- Revert:
  - `tools/workflow/run_cmd.py`
  - call-site changes in `tools/agent_eval/*`, `tools/coordination/run_automation.py`
  - new/updated tests and docs.
- Re-run:
  - `uv run --locked python tests/run.py --profile core`

## Outcomes & retrospective (fill when done)
- Root cause confirmed by red test: timeout path left orphan child process alive, which can stall later isolated review rounds.
- Implemented in `tools/workflow/run_cmd.py`:
  - process-group execution (`start_new_session=True`)
  - process-group termination on timeout (TERM -> KILL fallback)
  - inactivity timeout support (`idle_timeout_s`)
- Wired idle-timeout into reviewer-risk call paths:
  - `tools/agent_eval/run_pack.py`
  - `tools/agent_eval/run_scenario.py`
  - `tools/coordination/run_automation.py`
- Added deterministic regression:
  - `tests/contract/check_run_cmd_timeout_hardening.py`
- Updated contracts/docs:
  - `docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md`
  - `tests/contract/check_loop_contract_docs.py`
- Registry/doc sync:
  - `tests/manifest.json`
  - `docs/testing/TEST_MATRIX.md`
  - `docs/setup/TEST_ENV_INVENTORY.md`
- Verification:
  - `uv run --locked python tests/contract/check_run_cmd_timeout_hardening.py` PASS (red before fix, green after)
  - `uv run --locked python tests/agent_eval/check_pack_runner_and_grader_with_dummy_agent.py` PASS
  - `uv run --locked python tests/agent_eval/check_scenario_runner_and_grader_with_dummy_agent.py` PASS
  - `uv run --locked python tests/automation/check_run_automation_local.py` PASS
  - `uv run --locked python tests/contract/check_loop_contract_docs.py` PASS
  - `uv run --locked python tests/contract/check_test_registry.py` PASS
  - `uv run --locked python tests/run.py --profile core` PASS
  - `uv run --locked python tests/run.py --profile nightly` PASS
  - `lake build` PASS
