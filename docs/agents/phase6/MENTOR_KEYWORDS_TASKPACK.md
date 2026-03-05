# Phase6 Mentor Keyword TaskPack (v0)

Purpose: turn the mentor’s keyword list into an agent-eval task pack that is **regression-testable, stress-testable, and auditable**.

## 1) Keywords (required coverage set)

Original mentor keywords:
- “interial point” (very likely means *interior-point* / barrier methods)
- tangent plane (tangent plane inequality / supporting hyperplane / cutting plane)
- polynomial solvable (at least: explicit solvability + solvable-by-radicals direction)
- queueing theory (underlying recurrence / Lindley recursion, M/G/1)
- “little slot” (very likely means Little’s law in time-slot / sample-path form)

We standardize them as required keywords (mechanical checks):

- `interior_point`
- `tangent_plane`
- `polynomial_solvable`
- `queueing_lindley_recursion`
- `queueing_mg1`
- `littles_law`

Pack file:
- `tests/agent_eval/packs/mentor_keywords_v0/pack.yaml`

## 2) Task list (v0)

| task_id | keywords | expected | purpose |
|---|---|---|---|
| mk_convex_log_barrier | interior_point, tangent_plane | v0 TRIAGED / v1 SUCCESS | minimal formalizable example: tangent-plane inequality from log barrier style convexity |
| mk_queue_mg1_lindley | queueing_lindley_recursion, queueing_mg1 | v0 TRIAGED / v1 SUCCESS | cover “underlying recurrence + M/G/1” via Lindley recursion |
| mk_queue_littles_law_slot | littles_law | v0 TRIAGED / v1 SUCCESS | cover Little’s law via time-slot double counting |
| mk_poly_factorization_square | polynomial_solvable | v0 TRIAGED / v1 SUCCESS | cover explicit polynomial “solvable” via factorization |
| mk_poly_solvability_by_radicals | polynomial_solvable | v0 TRIAGED (BUDGET) / v1 SUCCESS | test budget recognition + reasonable downgrade + reuse of existing theorems (Abel–Ruffini direction) |

Note: SUCCESS/TRIAGED here are evaluation targets, not a promise. After the runner exists, these become stable PASS/FAIL checks.

### 2.5 Traceable references (mandatory)
To keep “classic theorem behind the keyword” traceable and verifiable:

- each `task.yaml: references` must use `REF:<id>` format
- full bibliographic info (including stable URLs) lives in `docs/references/mentor_keywords.yaml`
- each fixture problem directory’s `Sources.md` may only cite these `<id>`s

Core profile checks enforce this to prevent link drift and scattered low-quality references.

## 3) Mechanical gate: keyword coverage test
Core profile test:
- `tests/agent_eval/check_pack_keyword_coverage.py`

It verifies:
- `pack.yaml.required_keywords ⊆ ⋃ task.keywords`

## 4) Landed in v0 (Phase6.1)
- each task has a fixture problem: `tests/agent_eval/fixtures/problems/<problem_slug>/...`
- pack runner (v0): `tools/agent_eval/run_pack.py`
  - `--mode plan`: only generate Plan.json (CI/core)
  - `--mode materialize`: generate isolated workspaces + PROMPT.md (local/nightly)
  - `--mode run`: execute external agent via provider/profile (`--agent-provider`, optional `--agent-profile`) or legacy `--agent-cmd`
- deterministic grader (v0): `tools/agent_eval/grade_pack.py`
  - pure file/schema/field comparisons (no LLM)

Core profile tests:
- `tests/agent_eval/check_fixtures_exist.py`
- `tests/agent_eval/check_runner_plan_mode.py`

## 5) Next (Phase6.2+)
- scenario runner: three classes (interleaving / regression / pressure) written into contract + tests
- a standard non-interactive agent interface for provider/profile + trace/artifacts mounting rules (legacy `--agent-cmd` remains supported)
- add a small amount of rubric grading (only when deterministic checks cannot measure a dimension)
