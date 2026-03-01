---
name: leanatlas-agent-eval
description: Run Phase6 real agent evals (ProblemPacks & Scenarios). Generates deterministic plans, materializes per-run workspaces, and grades outputs with 0-LLM checks (schemas, patch-scope, evidence-chain, environment stamp).
---

# Skill: leanatlas-agent-eval

## Use when
- You need to run **real Phase6 evaluations**: ProblemPack or Scenario (interleaving/regression/pressure).
- You need to generate/check eval plans, materialize workspaces, and run deterministic grading (0-LLM).
- You need to confirm AttemptLog/RunReport/environment stamps/command evidence all satisfy the contracts.

## Don't use when
- You are writing the proof itself: use `.agents/skills/leanatlas-operator-proof-loop/SKILL.md`.
- You are running repository test suites: use `.agents/skills/leanatlas-run-workflow-tests/SKILL.md`.
- You are working on Dedup/Promotion/GC: use the corresponding Phase3 skills.

## Outputs
- `artifacts/agent_evals/<eval_id>/<stamp>/...`
  - Pack: `Plan.json`, `runs/**/PROMPT.md`, `runs/**/CONTEXT.json`, `AgentEvalReport.json`
  - Scenario: `ScenarioPlan.json`, `steps/**/{PROMPT.md,CONTEXT.json,AgentEvalReport.json}`, `ScenarioEvalReport.json`

## Must-run checks
(Pick Pack or Scenario depending on your task; run at least 2 commands.)

```bash
# Pack plan (structure checks + generate Plan.json)
uv run --locked python tools/agent_eval/run_pack.py \
  --pack tests/agent_eval/packs/<pack_id>/pack.yaml \
  --mode plan

# Scenario plan (structure checks + generate ScenarioPlan.json)
uv run --locked python tools/agent_eval/run_scenario.py \
  --scenario tests/agent_eval/scenarios/<scenario_id>/scenario.yaml \
  --mode plan

# Grading (requires existing run artifacts)
uv run --locked python tools/agent_eval/grade_pack.py \
  --eval-dir artifacts/agent_evals/<eval_id>/<stamp>

uv run --locked python tools/agent_eval/grade_scenario.py \
  --scenario-dir artifacts/agent_evals/<eval_id>/<stamp>/scenarios/<scenario_id>
```

## Notes
- Scenario defaults to `workspace_policy=SHARED`: runs intentionally share workspaces to catch sequence bugs where one fix causes a later regression.
- Any `SUCCESS` must pass `lake build`/linters (see `WORKFLOW_CONTRACT`) and leave verifiable evidence in AttemptLog.
