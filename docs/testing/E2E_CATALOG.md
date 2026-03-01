# E2E catalog (cases + scenarios)

This catalog exists for agents (including Codex) to understand *why* each E2E test exists, what it is supposed to catch, and what an acceptable fix looks like.

If you change or add an E2E test, you must update this file.

## E2E cases (`tests/e2e/golden/*`)

All E2E cases share the same structure:

- `tests/e2e/golden/<case_id>/case.yaml` defines metadata and execution budgets.
- `tests/e2e/golden/<case_id>/Problems/<case_id>/*.lean` is the isolated problem workspace.

### Smoke profile

- `smoke_missing_import`
  - Goal: verify the agent/tooling detects missing imports and fixes them *inside* the scoped problem.
  - Expected: SUCCESS.

- `smoke_missing_assumption`
  - Goal: verify the agent/tooling detects a missing assumption or lemma and corrects the proof *inside* the scoped problem.
  - Expected: SUCCESS.

- `smoke_trivial_rewrite`
  - Goal: verify basic rewriting works and the toolchain can build the edited file.
  - Expected: SUCCESS.

### Core profile

- `core_name_notation`
  - Goal: verify the agent can repair a proof involving name/notation issues.
  - Expected: SUCCESS.

- `core_budget_exhausted`
  - Goal: intentionally trigger a budget failure path to validate triage behavior.
  - Expected: TRIAGED (budget exhausted).

- `core_syntax_error`
  - Goal: validate error parsing and repair of a syntax mistake.
  - Expected: SUCCESS.

### Nightly profile

- `nightly_big_search`
  - Goal: heavier search/repair workload; exercises robustness and performance.
  - Expected: SUCCESS.

## E2E scenarios (`tests/e2e/scenarios/*/scenario.yaml`)

Scenarios are *multi-step* regressions.

They combine:

- `run_case` steps (execute a named E2E case)
- `patch` steps (apply a known patch)
- `run_cmd` steps (execute a deterministic command)
- `lake_build` steps (compile in the scenario workspace)

### Key semantics: `lake_build: Problems`

Scenario YAMLs often end with:

```yaml
- kind: lake_build
  target: Problems
```

`target: Problems` is a macro.

The runner expands it to "build the `build_target` of each prior `run_case` step that completed with final_status=SUCCESS".

This avoids false failures when the scenario intentionally includes triaged/error cases that should *not* be compiled.

### Smoke profile

- `scenario_cleanup_idempotence`
  - Goal: validate cleanup is idempotent and doesn't leave the workspace in a broken state.

- `scenario_toolbox_regression`
  - Goal: ensure a fix does not leak outside the problem scope (detect ERROR_OUTSIDE_SCOPE).

### Core profile

- `scenario_chain_core_3`
  - Goal: run a chain of three successful core cases and build their resulting targets.

- `scenario_chain_core_all`
  - Goal: exercise a broader selection including expected TRIAGED outcomes.

### Nightly profile

- `scenario_chain_nightly`
  - Goal: heavier nightly chain.

## Debugging guidance

- If you see `BUDGET_EXHAUSTED` on first run only:
  - increase budgets (prefer per-case `max_wall_time_ms`),
  - reuse `.lake` caches/workspaces,
  - disable mathlib cache downloads (`MATHLIB_NO_CACHE_ON_UPDATE=1`).

- Do **not** add blanket "retry-on-budget" rules. They hide real regressions.
