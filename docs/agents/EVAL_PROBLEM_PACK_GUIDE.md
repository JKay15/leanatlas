# Phase6 real task packs (ProblemPack) — design guide (v0)

Goal: Phase6 agent eval should not be “a demo run”. It should reproduce real proof-loop conditions and let us quantify:
- whether Codex truly **reuses existing tools first**
- whether skills/KB/automation growth **reduces toil**
- whether toolbox/seed growth is **healthy** (not overfitting / unnecessary deposition)

This guide specifies **structure and evidence chain**. The actual math tasks are provided by maintainers (you/mentor/team).

## 1) Task source requirements (must satisfy)
1) **Verifiable**: must compile/verify under Lean + mathlib (and LeanAtlas library as configured).
2) **Known answer**: we must know the correct solution direction in advance (otherwise this is not a real eval).
3) **Multiple variants**: at least two variants:
   - `v0_wrong_hint`: provide a plausible but wrong plan; expect Codex to TRIAGE with a complete evidence chain.
   - `v1_correct_hint`: provide the correct direction; expect SUCCESS (no `sorry`).
4) **Growth signal**: solving the task should trigger either:
   - ≥1 tool worthy of deposition (into a **test-only fixture toolbox**), or
   - ≥1 skill/KB addition suggested by mining + a Change Proposal.

## 2) Coverage dimensions (mentor keywords as natural domains)
The mentor keywords naturally split into three representative domains:

### A) convex optimization / convex analysis
- interior-point methods
- tangent plane inequality / supporting hyperplane

### B) queueing theory (sample-path first, probability later)
- Lindley recursion (GI/G/1 waiting time; M/G/1 is a special case)
- Little’s law (including time-slot / discrete-time variants)

### C) algebra (polynomials solvable)
- solvable by radicals / Galois theory (advanced; consider later Phase6 or Phase7)

## 3) Each task must declare expected deltas
Each `task.yaml` must include:
- expected `final_status` (SUCCESS or TRIAGED)
- if TRIAGED: expected `triage_family` / `triage_code`
- expected `tool_delta` (test fixture toolbox changes: count + key names)
- expected `skill_delta` (KB/skill changes: file paths + key bullets)
- expected `metrics_delta` (at least one), e.g.
  - rerun the same task with/without fixture toolbox: fewer retrieval steps, fewer attempts, TRIAGED→SUCCESS

## 4) Two recommended ways to build “known correct answer” tasks

### Method 1: mentor/you provide a correct proof skeleton
- GPTPro provides a natural-language skeleton
- Codex formalizes
- we record TRIAGED causes and design the wrong-hint variant accordingly

### Method 2: choose classics from authoritative references
- ensure the math result is authoritative
- translate into a Lean-friendly spec

## 5) Why the wrong-hint variant matters
In real usage, GPTPro will not always provide Lean-style proofs and will not always be correct.
Wrong-hint variants test:
- whether Codex will “blindly write code” instead of TRIAGING early
- whether triage evidence is auditable
- whether skills/KB growth triggers are real (not invented)

## 6) Interface to KB/skills growth
- each eval run produces AttemptLog/RunReport artifacts
- `tools/bench/mine_kb_suggestions.py` extracts pattern suggestions
- suggestions go through Change Proposals into KB/skills
- rerun evals to verify reduced toil (fewer TRIAGED, fewer attempts)

Related contracts:
- `docs/contracts/AGENT_EVAL_CONTRACT.md`
- `docs/contracts/SKILLS_GROWTH_CONTRACT.md`

## 7) Scenarios (sequence / regression / pressure)
A Pack is a set of independent runs. A Scenario is a **sequence across runs** to test interleaving/regression/pressure.

Directory:
- `tests/agent_eval/scenarios/<scenario_id>/scenario.yaml`

Commands:

```bash
# Plan (validate + expand steps)
uv run --locked python tools/agent_eval/run_scenario.py \
  --scenario tests/agent_eval/scenarios/<scenario_id>/scenario.yaml \
  --mode plan

# Materialize workspaces + step prompts
uv run --locked python tools/agent_eval/run_scenario.py \
  --scenario tests/agent_eval/scenarios/<scenario_id>/scenario.yaml \
  --mode materialize

# Run (requires a non-interactive agent command)
uv run --locked python tools/agent_eval/run_scenario.py \
  --scenario tests/agent_eval/scenarios/<scenario_id>/scenario.yaml \
  --mode run \
  --agent-cmd "<your_agent_cmd>"

# Grade (deterministic)
uv run --locked python tools/agent_eval/grade_scenario.py \
  --scenario-dir artifacts/agent_evals/<eval_id>/<stamp>/scenarios/<scenario_id>
```

Default `workspace_policy=SHARED` exists to catch state leaks, cleanup failures, and “fix introduced a new bug” sequence failures.
