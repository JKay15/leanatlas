---
title: Dynamic timeout policy with reconnect-aware grace (bounded)
owner: codex
status: done
created: 2026-03-05
---

## Purpose / Big Picture
Current timeout hardening prevents infinite hangs but uses mostly static thresholds. In practice, Codex CLI can show reconnect activity and then recover after long silence. This plan adds bounded, reconnect-aware dynamic grace while keeping deterministic hard fallback. Goal: avoid premature kill on recoverable reconnect periods, without allowing unbounded waiting.

## Glossary
- Reconnect marker: output line containing reconnect signal (e.g., "reconnecting").
- Dynamic grace: extra allowed wait window granted after reconnect markers.
- Bounded policy: grace is capped by max reconnect events and per-event grace seconds.

## Scope
In scope:
- `tools/workflow/run_cmd.py` reconnect-aware dynamic timeout policy.
- `tools/agent_eval/run_pack.py`, `tools/agent_eval/run_scenario.py`, `tools/coordination/run_automation.py` call-site integration for codex provider defaults.
- tests for reconnect-aware behavior.
- contract doc update for reconnect-aware bounded policy.

Out of scope:
- provider protocol changes.
- schema expansion for exec span fields.

## Interfaces and Files
- `run_cmd(..., reconnect_grace_s=?, reconnect_max_events=?, reconnect_pattern=?)`
- call sites pass policy only for reviewer-risk provider runs (default codex provider).

## Milestones
1) Red test
- Update `tests/contract/check_run_cmd_timeout_hardening.py` with reconnect-recovery case expected to pass with dynamic grace.
- Run test; expect fail before implementation.

2) Implement runner policy
- Add reconnect-marker scanning and bounded grace extension in `tools/workflow/run_cmd.py`.
- Keep static fallback (`timeout_s`, `idle_timeout_s`) mandatory.

3) Integrate provider defaults
- For `codex_cli`, default policy: `max_events=5`, `grace_s` configurable by env.
- Wire into pack/scenario/advisor execution paths.

4) Docs and verification
- Update `docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md` and doc guard test.
- Run targeted + core + nightly + `lake build`.

## Testing plan (TDD)
- Existing timeout hardening cases stay green.
- New case: command prints reconnect marker, stays silent past base idle timeout, then succeeds; run_cmd should not kill prematurely under reconnect policy.
- Guardrail: if reconnect limit exhausted, timeout still fires.

## Decision log
- 2026-03-05: choose bounded grace (not open-ended) to preserve deterministic upper bound and avoid infinite wait loops.

## Rollback plan
- Revert changes in run_cmd + call-site integration and docs.
- Re-run core profile to confirm rollback stability.

## Outcomes & retrospective (fill when done)
- Added bounded reconnect-aware dynamic timeout policy in `tools/workflow/run_cmd.py`:
  - new optional parameters: `reconnect_grace_s`, `reconnect_max_events`, `reconnect_pattern`
  - reconnect markers extend deadlines only within bounded caps
  - hard timeout + idle timeout fallback remains mandatory
- Integrated provider defaults (`codex_cli`: default max 5 reconnect events) into:
  - `tools/agent_eval/run_pack.py`
  - `tools/agent_eval/run_scenario.py`
  - `tools/coordination/run_automation.py` (advisor provider path)
- Expanded regression coverage:
  - `tests/contract/check_run_cmd_timeout_hardening.py` now includes reconnect-recovery case
  - red-before-green evidence: pre-implementation run failed with `TypeError` on missing reconnect parameters
- Contract/doc updates:
  - `docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md`
  - `tests/contract/check_loop_contract_docs.py`
- Independent `codex exec` review was attempted twice and triaged as tooling stall:
  - `artifacts/reviews/20260305_dynamic_timeout_reconnect_policy_codex_exec_review_attempts.md`
  - `artifacts/reviews/20260305_dynamic_timeout_reconnect_policy_codex_exec_review_round1.md`
- Verification:
  - `uv run --locked python tests/contract/check_run_cmd_timeout_hardening.py` PASS
  - `uv run --locked python tests/contract/check_loop_contract_docs.py` PASS
  - `uv run --locked python tests/agent_eval/check_pack_runner_and_grader_with_dummy_agent.py` PASS
  - `uv run --locked python tests/agent_eval/check_scenario_runner_and_grader_with_dummy_agent.py` PASS
  - `uv run --locked python tests/automation/check_run_automation_local.py` PASS
  - `uv run --locked python tests/automation/check_run_automation_provider_visibility.py` PASS
  - `uv run --locked python tests/run.py --profile core` PASS
  - `uv run --locked python tests/run.py --profile nightly` PASS
  - `lake build` PASS
