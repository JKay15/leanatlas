# Agent Evaluation Tests

This folder contains **deterministic scaffolding** for Phase6 agent evaluation.

The goal is to test an agent’s *workflow discipline* (proof-loop evidence) and *triage behavior*,
not just whether a Lean theorem can be proven.

## What lives here

- `fixtures/problems/<problem_slug>/...`
  - minimal Lean problems used as starting states

- `tasks/<task_id>/task.yaml`
  - one task = one fixture problem + multiple prompt variants
  - validated by `docs/schemas/AgentEvalTask.schema.json`

- `packs/<pack_id>/pack.yaml`
  - a list of tasks (optionally selecting variants)
  - used by the pack runner (`tools/agent_eval/run_pack.py`)

- `scenarios/<scenario_id>/scenario.yaml`
  - **Phase6.2**: sequences of runs + maintainer overlays
  - validated by `docs/schemas/AgentEvalScenario.schema.json`

## Deterministic validation (CI-friendly)

### Validate task YAML

```bash
python tests/agent_eval/validate_tasks.py
```

### Validate scenario YAML

```bash
python tests/agent_eval/validate_scenarios.py
```

## Running a pack (local)

```bash
python tools/agent_eval/run_pack.py \
  --pack tests/agent_eval/packs/mentor_keywords_v0/pack.yaml \
  --mode materialize
```

Then run your agent on the materialized runs, and grade:

```bash
python tools/agent_eval/grade_pack.py --eval-dir <the generated eval dir>
```

## Running a scenario (local)

Scenarios simulate sequence effects (triage → maintainer patch → success, regressions, pressure).

Plan/expand only:

```bash
python tools/agent_eval/run_scenario.py \
  --scenario tests/agent_eval/scenarios/mentor_keywords_interleaving_v0/scenario.yaml \
  --mode plan
```

Materialize a shared workspace:

```bash
python tools/agent_eval/run_scenario.py \
  --scenario tests/agent_eval/scenarios/mentor_keywords_interleaving_v0/scenario.yaml \
  --mode materialize
```

Run with provider/profile (preferred):

```bash
python tools/agent_eval/run_scenario.py \
  --scenario tests/agent_eval/scenarios/mentor_keywords_interleaving_v0/scenario.yaml \
  --mode run \
  --agent-provider codex_cli
```

Legacy command mode:

```bash
python tools/agent_eval/run_scenario.py \
  --scenario tests/agent_eval/scenarios/mentor_keywords_interleaving_v0/scenario.yaml \
  --mode run \
  --agent-cmd "codex ..."
```

Grade:

```bash
python tools/agent_eval/grade_scenario.py --eval-dir <the generated eval dir>
```
