# AGENT_EVAL_CONTRACT v0 (Phase6)

Purpose: turn “can Codex actually do real work under the LeanAtlas workflow?” into a **regression-testable, auditable, pressure-testable** engineering object.

Phase1/2/3 e2e tests mostly validate LeanAtlas deterministic gates.
Phase6 agent evals validate: **under those gates, can Codex reliably advance real tasks without hallucinating its way out?**

## 0) Core principles (mandatory)

1) **Real workflow first**
   - Evaluations must simulate the LeanAtlas small loop: snapshot → retrieval → attempt → judge → reports.
   - Not just “unit test a helper function”.

2) **Evidence first**
   - Any PASS must have a complete evidence chain:
     - RunReport
     - AttemptLog
     - RetrievalTrace
   - No evidence ⇒ FAIL.

3) **Regressable**
   - Same task + same pinned tool versions + same inputs ⇒ same PASS/FAIL.

4) **Layered scoring**
   - **Deterministic checks** (hard gate): 0‑LLM, reproducible.
   - **Rubric scoring** (soft score): allowed only for “quality dimensions” where hard checks are insufficient.
     - May be rules-based or LLM-as-judge.
     - Must be version-pinned and reproducible (see §4).

## 1) Terms

- **Agent eval task**: one real task (proof-loop, promotion, GC, domain extension, automation).
- **Variant**: multiple input versions of one task, used to simulate the big loop (e.g. wrong GPTPro hint → TRIAGED → corrected hint → SUCCESS).
- **Oracle pack (external)**: evaluator-held “known answers / expected tools / expected skill updates”.
  - Not committed to the repo by default (prevents the agent from reading answers).

## 2) Directories and sources of truth

Committed to repo:
- Task definitions: `tests/agent_eval/tasks/<task_id>/task.yaml`
- Task schema: `docs/schemas/AgentEvalTask.schema.json`
- Fixtures: `tests/agent_eval/fixtures/problems/<problem_slug>/{Spec,Proof,Cache,Scratch}.lean`

Not committed (generated artifacts):
- Eval artifacts: `artifacts/agent_evals/<eval_id>/<stamp>/...`

External by default:
- Oracle packs: `~/.cache/leanatlas/oracle/<oracle_pack_id>/...`

Rules:
- repo commits only public expectations (structure + metrics), not full solutions.
- shortest proofs / full expected deposition sets belong in the Oracle pack unless explicitly approved.

## 2.5) Runner tools (v0)

V0 provides deterministic scripts:

Plan / workspace materialization:
- `uv run --locked python tools/agent_eval/run_pack.py --pack <pack.yaml> --mode plan`
- `uv run --locked python tools/agent_eval/run_pack.py --pack <pack.yaml> --mode materialize`

Deterministic grading (0‑LLM):
- `uv run --locked python tools/agent_eval/grade_pack.py --eval-dir artifacts/agent_evals/<eval_id>/<stamp>`

Runner behavior:
- `--mode plan`: validate schemas and pack composition; output `Plan.json` (fast; CI/core).
- `--mode materialize`: for each (task,variant), create an isolated workspace (repo copy + fixture copy) and write `PROMPT.md`.
  - also writes `BaselineToolSurface.json` captured by the runner; used to score tool reuse deterministically.
- `--mode run`: on top of materialize, executes an external agent command via `tools/workflow/run_cmd.py` (requires `--agent-cmd`).

Notes:
- `PROMPT.md` enables a strict non-interactive run that still follows LeanAtlas workflow/contracts.
- **Framework auth is agent-specific**: runners require `--agent-cmd`; any API keys are only needed if your chosen agent implementation requires them.
- grading depends strictly on artifacts. Missing required evidence ⇒ FAIL.
  - `pins_used.json` is **runner-owned** and MUST be present (runner ensures this).

## 3) Task.yaml field-level contract

Tasks must satisfy schema: `leanatlas.agent_eval_task`.

### 3.1 References (traceable sources, mandatory)
To prevent “storytelling proofs”, each task must include traceable references:

- `task.yaml: references` must be a **non-empty list**
- each entry must be `REF:<id>` (no raw URLs in task files)
- `<id>` must exist in `docs/references/*.yaml`

CI must validate:
- `REF:<id>` is resolvable
- fixture `Sources.md` references only known `<id>`s

### Minimal required fields (V0)
- `task_id`: globally unique.
- `kind`: task kind (`PROOF_LOOP` / `PROMOTION` / `GC` / `DOMAIN` / `AUTOMATION`).
- `prompt`: instructions to Codex (real-world tone).
- `variants[]`: at least 1.

Each variant must include:
- `variant_id`: unique.
- `gptpro_hint`: upstream hint (may be empty).
- `expected.final_status`: `SUCCESS` or `TRIAGED`.
- if TRIAGED: `expected.triage_family` (coarse family).

Strongly recommended for growth eval:
- `tool_delta`: expected additions/promotions in a **test-only fixture toolbox** (module or decl names).
- `skill_delta`: expected KB/skill suggestions (tags or file paths).
- `oracle.oracle_pack_id`: optional; if provided, runner may load richer expectations.

## 4) Rubric grader (what it is, why it exists)

- **Rubric**: a scoring checklist that breaks “quality” into small judgeable dimensions.
  Examples: evidence completeness, error localization accuracy, wheel-reinvent rate, forbidden-edit attempts, reusable-tool deposition quality.

- **Rubric grader**: the program that applies the rubric.
  - It may be deterministic rules or LLM-as-judge.

V0 constraints:
- rubric grading may not replace deterministic gates; it only adds extra dimensions.
- rubric grader must:
  - read only from artifacts (RunReport / RetrievalTrace / AttemptLog) as inputs
  - produce fixed-format outputs in AgentEvalReport
  - be version pinned (model + scripts recorded in pins)

## 5) AgentEvalReport field-level contract

Every PASS/FAIL must land in auditable files.

Locations:
- per-run report:
  - `artifacts/agent_evals/<eval_id>/<stamp>/runs/<task_id>/<variant_id>/AgentEvalReport.json`
- pack aggregate:
  - `artifacts/agent_evals/<eval_id>/<stamp>/PackEvalReport.json`

Single-run schema: `docs/schemas/AgentEvalReport.schema.json`.

Minimal V0 fields:
- `task_id`, `variant_id`
- `passed` (bool)
- `deterministic_checks[]` (each check id + passed + evidence refs)
- `signals` (numeric metrics for trend/regression)

Rules:
- Missing artifacts/evidence ⇒ FAIL.
- Rubric scores may be appended, but cannot replace deterministic gates.

## 6) Scenario classes (Phase6.2)

Scenarios cover sequence effects not visible in single runs:

- **Interleaving**: SUCCESS → TRIAGED → fix → a *new* TRIAGED (patch-scope traps, imports, domain prune mistakes, …)
- **Regression**: same problem under different tool-surface states (empty toolbox / fixture toolbox / fixture GC’d) must behave stably
- **Pressure**: many problems + large retrieval traces + repeated clean/run; must not accumulate garbage or become exponentially slower

Contract and schema:
- `docs/contracts/AGENT_EVAL_SCENARIO_CONTRACT.md`
- `docs/schemas/AgentEvalScenario.schema.json`

## 7) Relationship to tool/skill growth
Agent eval must answer:
1) tool deposition is “just right”: not too many, not too few, and reusable across tasks.
2) skills/KB are growing: new patterns are captured and measurably improve later runs.

Skill growth standard:
- `docs/contracts/SKILLS_GROWTH_CONTRACT.md`
