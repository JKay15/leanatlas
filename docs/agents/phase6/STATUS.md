# Phase 6 Status

As of **2026-02-24**.

## Phase6.1 Tasks and Pack (Mentor Keywords v0)

- ✅ 5 fixture problems
- ✅ 5 `task.yaml` entries (each with multiple variants: SUCCESS / fixable hint / TRIAGED)
- ✅ Pack file: `tests/agent_eval/packs/mentor_keywords_v0/pack.yaml`
- ✅ Pack runner: `tools/agent_eval/run_pack.py` (plan/materialize)
- ✅ Pack grader: `tools/agent_eval/grade_pack.py`
- ✅ Machine gates:
  - `tests/agent_eval/validate_tasks.py`
  - `tests/agent_eval/check_pack_keyword_coverage.py`
  - `tests/agent_eval/check_runner_plan_mode.py`

## Phase6.2 Three scenario classes

- ✅ Schema: `docs/schemas/AgentEvalScenario.schema.json`
- ✅ Contract: `docs/contracts/AGENT_EVAL_SCENARIO_CONTRACT.md`
- ✅ Scenarios:
  - `mentor_keywords_interleaving_v0` (INTERLEAVING)
  - `mentor_keywords_regression_v0` (REGRESSION)
  - `mentor_keywords_pressure_v0` (PRESSURE)
- ✅ Runner: `tools/agent_eval/run_scenario.py` (plan/materialize/run)
- ✅ Grader: `tools/agent_eval/grade_scenario.py`
- ✅ Machine gates:
  - `tests/agent_eval/validate_scenarios.py`
  - `tests/agent_eval/check_scenario_class_coverage.py`
  - `tests/agent_eval/check_scenario_runner_plan_mode.py`

## Next (6.3+)

- Integrate scenario `run` mode into nightly tier (real agent execution).
- Add hard-violation scenarios: OPERATOR patch-scope violations, import pollution, incorrect domain-prune deletions.
- Build browsable dashboards for reports (failure clustering, frequent triage codes, missing-evidence rates).
