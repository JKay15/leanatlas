# AgentEval Scenario Contract

This contract defines **scenario-level** evaluation for Phase6.

A *scenario* is a deterministic, declarative sequence of steps that can:
- run multiple AgentEval tasks (possibly repeatedly)
- apply maintainer overlays between runs (simulating the big-loop “Advisor → Maintainer → Operator” handoff)
- introduce regressions and recovery (toolbox state changes)
- stress the runner with repeated clean/run cycles

Scenarios exist to test **sequence effects** that single-run packs cannot cover:
- interleaving: SUCCESS → TRIAGED → maintainer fix → SUCCESS → …
- regression: same task under different toolbox states
- pressure: many runs + lots of logs + repeated clean

## Inputs

### Scenario YAML

Location:

- `tests/agent_eval/scenarios/<scenario_id>/scenario.yaml`

Schema:

- `docs/schemas/AgentEvalScenario.schema.json`

Key fields:

- `scenario_id`: stable identifier
- `scenario_class`: `INTERLEAVING | REGRESSION | PRESSURE`
- `tier`: `core | smoke | nightly | manual`
- `execution.enabled`: if `false`, tooling may still validate the file but should not run it
- `execution.workspace`: currently **only** `shared`
- `steps`: ordered list of steps

### Step kinds

#### `run_task`

Runs a single `(task_id, variant_id)` pair.

- `task_id`: `tests/agent_eval/tasks/<task_id>/task.yaml`
- `variant_id`: one of that task’s variants
- `reset_problem` (optional, default `true`):
  - `true`: re-copy the fixture into `workspace/Problems/<problem_slug>` before running
  - `false`: keep the current on-disk problem state (useful right after a maintainer overlay)
- `expected_override` (optional): overrides the task variant’s `expected` block for this scenario step.
  - Use this sparingly (mostly for regression-induced TRIAGED steps).

#### `run_pack`

Expands a pack into multiple `run_task` steps.

- `pack_id`: `tests/agent_eval/packs/<pack_id>/pack.yaml`
- `repeat` (optional, default `1`): repeats the expanded run list
- `task_variants` (optional): map `{task_id: [variant_id, ...]}` to restrict variants.
  - If omitted, all variants are included.

#### `apply_overlay`

Applies a directory overlay onto the shared workspace.

- `mode`: `MAINTAINER` or `OPERATOR`
  - `MAINTAINER` overlays may touch any file (used to simulate external fixes)
  - `OPERATOR` overlays are intended for testing patch-scope enforcement; keep them rare
- `overlay`: path **relative to the scenario directory**

Overlay semantics:

- All files under `<scenario_dir>/<overlay>` are copied onto `eval_dir/workspace/` (overwrite allowed).
- This is performed by the runner (deterministic), not by the agent.

#### `clean`

Performs runner-defined cleanup in the shared workspace.

Current default behavior:

- removes `workspace/Problems/*/Reports/*` and scratch artifacts
- does **not** touch pinned toolchain state

This is a future extension point; do not rely on exact implementation details.

#### `lake_build`

Runs `lake build <target>` in the shared workspace.

Used for:

- regression checks when you want a pure build gate instead of an agent run

#### `run_cmd`

Runs an arbitrary command array.

Used sparingly:

- in nightly pressure scenarios
- for instrumentation

## Outputs

Scenario runs write to:

- `artifacts/agent_evals/scenarios/<scenario_id>/<stamp>/`

Layout:

- `ScenarioSource.yaml` — a copy of the input scenario file (self-contained review)
- `Plan.json` — expanded step list and resolved references
- `BaselineToolSurface.json` — runner-produced baseline tool surface snapshot (before step 0)
- `workspace/` — shared workspace
- `runs/<step_id>/`
  - `PROMPT.md`
  - `CONTEXT.json`
  - `AgentEvalReport.json` (after grading)
  - `agent_exec_span.json` (if the runner executed an external agent command)
  - `ToolSurface.json` — runner-produced tool surface snapshot at the end of this step
- `ScenarioEvalReport.json` — scenario-level summary

### Tool surface snapshots

`ToolSurface.json` and `BaselineToolSurface.json` have the same shape:

- `tool_files`: list of `.lean` source file paths under:
  - `LeanAtlas/Toolbox/**`
  - `LeanAtlas/Incubator/Seeds/**`
  - `LeanAtlas/Incubator/External/**`
- `tool_modules`: the corresponding Lean module names inferred from those paths

These are produced by the runner (deterministic), **not** by the agent.

### Scenario-level tool reuse report

`ScenarioEvalReport.json` (schema: `docs/schemas/AgentEvalScenarioReport.schema.json`) may include:

- `tool_reuse`: deterministic scoring of scenario-level tool reuse.

Key ideas:

- **Introduced tool module**: a module that appears in `ToolSurface.json` for step *i* but not in step *i-1*.
  - Typical source: a `MAINTAINER apply_overlay` that simulates promotion into `Toolbox`.
- **Reused tool module**: an introduced module that becomes *reachable* from the imports of any later `run_task` proof.
  - Reachability is computed via a local import graph built from `workspace/LeanAtlas/**/*.lean`.
  - This is a necessary condition for real reuse and is fully deterministic.

Hard gate:

- `run_task` steps (OPERATOR) must not introduce tool modules.
  - If `ToolSurface.json` changes during a `run_task`, the scenario fails even if logs “look fine”.
  - This catches patch-scope breaches that a faulty agent log might miss.

## Execution

The scenario runner supports 3 modes:

- `plan`: validate + expand steps; write `Plan.json` (runner may still materialize workspace for inspection)
- `materialize`: create workspace + write prompts/contexts; **no agent execution**
- `run`: additionally execute the agent command for each `run_task` step

Typical local workflows:

- Plan only:
  - `python tools/agent_eval/run_scenario.py --scenario tests/agent_eval/scenarios/<id>/scenario.yaml --mode plan`

- Materialize:
  - `python tools/agent_eval/run_scenario.py --scenario ... --mode materialize`

- Run with Codex (or another agent runner):
  - `python tools/agent_eval/run_scenario.py --scenario ... --mode run --agent-cmd "codex ..."`

Grading:

- `python tools/agent_eval/grade_scenario.py --eval-dir <scenario_eval_dir>`

## Determinism and anti-hallucination

Scenario tooling MUST be deterministic:

- use schema validation
- resolve all file paths explicitly
- record command execution evidence using `tools/workflow/run_cmd.py` spans

The agent is not trusted to “describe what happened”; the runner must capture it.
