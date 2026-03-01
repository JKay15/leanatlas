# Phase3 PromotionGate

Owner: Maintainers

Status: Draft

Created: 2026-02-26

## Purpose / Big Picture

This ExecPlan defines a deterministic “promotion gate” for Phase3 changes: given a repo checkout, we can validate that promotions (copying curated changes into the main working tree) are correct, reproducible, and do not regress the Phase3 E2E golden suite.

The big idea: the **runner** should be the source of truth for what to do, and the gate should be **auditable** via artifacts.

## Progress

- Defined baseline workflows and contracts.
- Wired scenarios to exercise promotion (apply), plus E2E validation.

## Surprises & Discoveries

- Python entrypoints invoked as scripts can fail to import repo modules unless `sys.path` is explicitly bootstrapped or the interpreter’s CWD is correct.
- Building aggregate targets like `Problems` is brittle; building the set of previously-successful module targets is more stable and produces clearer failures.

## Decision Log

- Use `--profile` everywhere (single canonical flag).
- Prefer runner-owned artifact generation for hard gates (e.g. `pins_used.json`) when possible.
- Keep ExecPlans free of fenced code blocks so they can be embedded into other prompt formats without conflicting delimiters.

## Outcomes & Retrospective

Success looks like:

- Promotion scenarios run end-to-end.
- Artifacts include step-level JSON and command logs.
- Failures are actionable (rc + diagnostics + output tail).

## Context and Orientation

Key files:

- Scenario runner: `tests/e2e/run_scenarios.py`
- Scenarios: `tests/e2e/scenarios/*/scenario.yaml`
- Promotion tool: `tools/promote/promote.py`
- Contracts: `docs/contracts/*.md`

## Plan of Work

1) Validate schemas and contracts.
2) Run the Phase3 promotion scenarios.
3) Ensure artifacts are present and self-explanatory.
4) If failures occur, fix the root cause (imports, profiles, cache behavior) rather than masking with retries.

## Concrete Steps

- Run scenario suite (core):

    uv run --locked python tests/e2e/run_scenarios.py --profile core

- Run a single scenario:

    uv run --locked python tests/e2e/run_scenarios.py --scenario scenario_phase3_gc_apply_smoke

- If you need to preserve a workdir for debugging:

    uv run --locked python tests/e2e/run_scenarios.py --scenario scenario_phase3_gc_apply_smoke --keep-workdir

## Validation and Acceptance

Acceptance checks:

- Scenario runner exits 0.
- Each scenario produces `ScenarioReport.json`.
- Each step produces a corresponding `*_step.json` artifact.
- If a `lake_build` step fails, its artifact includes:
  - `expanded_targets`
  - `failed_target`
  - `output_tail`
  - parsed `diagnostics`

## Idempotence and Recovery

- Re-running the same scenario should be safe.
- Prefer shared workspaces that preserve `.lake/` dependencies, but reset sources between scenarios.
- Do not introduce “retry-on-budget” logic to soak/scenario runners; fix budgets and dependency caching instead.

## Artifacts and Notes

- Scenario artifacts live under:

    .cache/leanatlas/e2e_scenarios/<scenario_id>__<run_id>/artifacts/

- Command logs (for `run_cmd` steps) live under per-scenario `cmd/` directories.
