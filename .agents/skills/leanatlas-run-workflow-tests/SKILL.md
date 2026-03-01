---
name: leanatlas-run-workflow-tests
description: Run LeanAtlas workflow tests (contracts, cases, scenarios, stress) locally and summarize failures with pointers to artifacts.
---

## Use when
- You changed workflow tooling/contracts/tests and need to confirm the LeanAtlas test matrix still passes.
- You need a reproducible failure report with artifact paths (instead of a vague summary).

## Don't use when
- You are doing single-problem proof work under `Problems/**` and did not touch the platform.
- You cannot run the pinned Lean/mathlib toolchain but the test tier requires it.

## Outputs
- Console summary (pass/fail)
- Artifact pointers under `artifacts/**` and `.cache/leanatlas/**` for the first failing test

## Must-run checks
- `./.venv/bin/python tests/run.py --profile core` (preferred when `.venv` exists)
- `./.venv/bin/python tests/e2e/run_cases.py --profile smoke` (preferred when `.venv` exists)

Fallback when `.venv` is missing:
- `uv run --locked python tests/run.py --profile core`
- `uv run --locked python tests/e2e/run_cases.py --profile smoke`

If you changed Phase6 agent-eval (pack/scenario runners), also run:
- `./.venv/bin/python tests/agent_eval/check_runner_plan_mode.py`
- `./.venv/bin/python tests/agent_eval/check_scenario_runner_plan_mode.py`
- `./.venv/bin/python tests/agent_eval/validate_scenarios.py`

## Fast entrypoints (Lake)
- Lint discipline (deterministic, no Lean needed): `lake lint`
- Core workflow tests (deterministic, no Lean needed): `lake test`

## Extended execution tests (requires Lean + mathlib)
- E2E cases:
  - `./.venv/bin/python tests/e2e/run_cases.py --profile smoke`
  - `./.venv/bin/python tests/e2e/run_cases.py --profile core`
- Sequence scenarios:
  - `./.venv/bin/python tests/e2e/run_scenarios.py --profile core`
- Stress/soak (nightly):
  - `./.venv/bin/python tests/stress/soak.py --iterations 20 --profile core --shuffle --seed 0`

## Failure handling
If any test fails:
1) Locate artifacts under `artifacts/**` or `.cache/leanatlas/**`.
2) Summarize the first failing step.
3) Cite the relevant file paths (report + log paths).
