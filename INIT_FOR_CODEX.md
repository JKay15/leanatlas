# Maintainer initialization checklist (Codex)

This repository is designed to be initialized by an agent (Codex) in **Maintainer** mode.

The goal is boringly practical:

* after this checklist passes, a user can switch to **Operator** mode and start formalizing proofs,
* the local harnesses (tests, Phase6 eval, automations) behave predictably,
* failures are surfaced as actionable artifacts (not mystery).

This checklist is intentionally **executable**: every item has a concrete command to run and a pass/fail condition.

## Operating rules

1) Prefer **fixing root causes** over adding retries.
   *Do not* add “budget jitter” / retry-on-triage logic to soak or eval runners.

2) Run commands using the repo Python:

* preferred: `./.venv/bin/python ...`
* acceptable: `uv run --locked python ...`

Never assume the system Python has dependencies.

3) Keep the repo clean:

* no `__pycache__/` or `*.pyc`
* no large generated artifacts committed

## Step 0 — Sanity checks

Run:

```bash
pwd
ls
```

Pass when:

* you are at the repo root (contains `AGENTS.md`, `tests/`, `tools/`).

## Step 0.5 — Preflight (idempotency gate)

Run:

```bash
test -x ./.venv/bin/python && echo "venv:present" || echo "venv:missing"
./.venv/bin/python -c "import yaml, jsonschema; print('deps-ok')" || true
lake --version
```

Pass when:

* all checks succeed, meaning setup prerequisites are already satisfied.

Behavior:

* if preflight passes, skip redundant install/update actions in Step 1 and continue with verification gates.
* if preflight fails, execute Step 1 normally.

## Step 1 — Python environment is real

Run:

```bash
uv --version
uv sync --locked
./.venv/bin/python -c "import yaml, jsonschema; print('deps-ok')"
```

Pass when:

* `deps-ok` prints,
* no missing-module errors.

If Step 0.5 already passed fully, Step 1 may be marked as "satisfied" and skipped.

## Step 2 — Contract + schema suite (fast gate)

Run:

```bash
./.venv/bin/python tests/run.py --profile core
```

Pass when:

* all core-tier tests pass.

If it fails:

* fix the failure,
* re-run until it passes.

## Step 3 — Core tier (default gate)

Run:

```bash
./.venv/bin/python tests/run.py --profile core
```

Pass when:

* all core-tier tests pass.

## Step 4 — Automation registry is valid

Run:

```bash
./.venv/bin/python tests/automation/run_dry_runs.py
```

Pass when:

* every automation in `automations/registry.json` dry-runs successfully,
* the output includes a pass summary.

## Step 5 — Phase6 harness: dummy run must grade cleanly

This proves the runner + grader contract (paths, required files, hard gates).

Run a single dummy pack attempt:

```bash
./.venv/bin/python tools/agent_eval/run_pack.py --mode dummy --limit 1
./.venv/bin/python tools/agent_eval/grade_pack.py --latest
```

Pass when:

* the grader reports `passed=true` for the dummy attempt.

Important:

* `pins_used.json` is runner-owned. If it’s missing, treat as a harness bug.

## Step 6 — Phase6 harness: plan mode generates stable prompts

Run:

```bash
./.venv/bin/python tools/agent_eval/run_pack.py --mode plan --limit 1
./.venv/bin/python tools/agent_eval/run_scenario.py --mode plan --limit 1
```

Pass when:

* each run writes a `PROMPT.md` into the attempt directory,
* no crashes.

## Step 7 — E2E runners validate their inputs

Run:

```bash
./.venv/bin/python tests/e2e/validate_cases.py
./.venv/bin/python tests/e2e/validate_scenarios.py
```

Pass when:

* all case/scenario YAML validates against schemas.

## Step 8 — Optional but recommended: soak smoke pass

This is the first “real Lean build” canary.

Run:

```bash
./.venv/bin/python tests/stress/exec_soak_smoke.py
```

Pass when:

* it completes without `TRIAGED/BUDGET_EXHAUSTED` on `expected=SUCCESS`.

Notes:

* `tests/stress/soak.py` seeds its `.lake/` deps from the shared E2E cache to avoid re-cloning mathlib.
* `tests/e2e/run_scenarios.py` sets `MATHLIB_NO_CACHE_ON_UPDATE=1` during `lake build` to avoid hanging cache fetches.

## Step 9 — Documentation pointers stay accurate

Run:

```bash
./.venv/bin/python tests/contract/check_agents_navigation_coverage.py
./.venv/bin/python tests/contract/check_test_matrix_up_to_date.py
```

Pass when:

* navigation coverage passes,
* `docs/testing/TEST_MATRIX.md` is up to date.

If the matrix is stale, regenerate it:

```bash
./.venv/bin/python tools/tests/generate_test_matrix.py > docs/testing/TEST_MATRIX.md
```

## Done state

Initialization is considered complete when:

* Steps 0–7 pass,
* `tests/run.py --profile core` passes,
* Phase6 dummy + grading works,
* no new contract failures remain.

At that point:

* switch to Operator workflow (`docs/agents/OPERATOR_WORKFLOW.md`),
* optionally configure Codex App automations using `docs/agents/CODEX_APP_PROMPTS.md`.
