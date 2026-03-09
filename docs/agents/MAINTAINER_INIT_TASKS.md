# Maintainer initialization tasks

This checklist is for maintainers setting up a fresh clone and bringing the repo into a known-good state.

It is written to be *Codex-executable*: each item should be doable by a maintainer agent reading the repository, running commands, and producing artifacts.

## 0. Ground rules

- **Never rely on system Python.** Use a repo-local `.venv` or `uv run --locked`.
- **Profiles are inclusive**: `core` includes `smoke`; `nightly` includes `core`; `soak` includes `nightly`.
- **Do not paper over failures with retries.** If something flakes (e.g. `BUDGET_EXHAUSTED`), fix root causes (budgets, caching, workspace reuse).

## 1. One-time machine prerequisites

- [ ] `uv` installed and available on PATH.
- [ ] Lean toolchain installed (Lean 4 / `lake`).
- [ ] Git installed and able to clone dependencies.

Acceptance criteria:
- `uv --version` works.
- `lake --version` works.

## 2. Repo-local Python environment

- [ ] Create a locked, repo-local virtualenv:

  - `uv sync --locked`

- [ ] Verify imports required by the test harness:

  - `.venv/bin/python -c "import yaml, jsonschema"`

Acceptance criteria:
- `.venv/bin/python` exists.
- The import check succeeds.

## 3. Contract and schema gates

Run the minimal gate first:

- [ ] `.venv/bin/python tests/run.py --profile smoke`

Then the default developer gate:

- [ ] `.venv/bin/python tests/run.py --profile core`

Acceptance criteria:
- Both profiles complete with exit code 0.
- `docs/testing/TEST_MATRIX.md` matches `tests/manifest.json` (the contract check enforces this).

## 4. E2E cases and scenarios (Lean-backed)

Run E2E cases:

- [ ] `.venv/bin/python tests/e2e/run_cases.py --profile smoke`
- [ ] `.venv/bin/python tests/e2e/run_cases.py --profile core`

Run E2E scenarios:

- [ ] `.venv/bin/python tests/e2e/run_scenarios.py --profile smoke`

Acceptance criteria:
- All smoke/core E2E runs produce `artifacts/e2e/RunReport.json` and exit 0.
- Scenario reports include expanded lake targets when `lake_build: Problems` is used.

## 5. Phase 6 real-agent evaluation (runner + grader)

The Phase 6 pipeline has three layers:

- **User layer**: run a pack/scenario and get a pass/fail + artifacts.
- **Developer layer**: debug using `--mode plan` / `--mode materialize`.
- **Automation layer**: schedule these checks and persist results.

Tasks:

- [ ] Validate that the runner writes `pins_used.json` automatically.

  Runner-owned output path:
  `Problems/<problem_slug>/Reports/<run_id>/pins_used.json`

- [ ] Run a tiny pack with the dummy agent:

  - `.venv/bin/python tools/agent_eval/run_pack.py --mode run --limit 1 --agent-provider codex_cli --pack tests/agent_eval/packs/phase6_smoke.json`
  - legacy local dummy path: `.venv/bin/python tools/agent_eval/run_pack.py --mode run --limit 1 --agent-cmd "python tools/agent_eval/dummy_agent.py" --pack tests/agent_eval/packs/phase6_smoke.json`

- [ ] Grade it:

  - `.venv/bin/python tools/agent_eval/grade_pack.py --run-dir artifacts/agent_eval/<eval_id>/<pack_id>`

Acceptance criteria:
- The run directory contains `RunReport.json`, `AttemptLog.jsonl`, and `pins_used.json`.
- Grading passes for the dummy pack.

## 6. Stress/soak

Soak is allowed to be slow, but it must be *explainably slow* (not deadlocked on cache downloads).

- [ ] Run the smoke soak:

  - `.venv/bin/python tests/stress/exec_soak_smoke.py`

Notes:
- The soak runner tries to reuse `.lake` from the shared E2E workspace to avoid re-cloning `mathlib4`.
- The soak runner sets `MATHLIB_NO_CACHE_ON_UPDATE=1` to avoid blocking on cache downloads.

Acceptance criteria:
- The smoke soak finishes with exit code 0.

## 7. Codex App setup (optional but recommended)

Maintainers should wire scheduled maintenance into Codex App Automations.

- [ ] Read `docs/agents/AUTOMATIONS.md` and `automations/registry.json`.
- [ ] Create the matching Codex App Automations (names/schedules/prompts).
- [ ] Perform a dry-run of each automation and paste the run output into the repo (or attach it to the PR).

Acceptance criteria:
- Every `status=active` automation in `automations/registry.json` has a dry-run that succeeds.

## 8. Documentation hygiene

- [ ] All shipped docs are English-only.
- [ ] No `__pycache__/` artifacts are committed or shipped.

Acceptance criteria:
- `git status` clean.
- A search for CJK characters in the repo returns no matches.
