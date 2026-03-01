# Test Intents

This document exists for one reason: **agents (and humans) should not have to reverse-engineer the purpose of each test from code.**

If a test fails, your first job is to understand *what invariant it is defending*.

## 1) Contract tests (tests/contract)

Contract tests protect repo-wide invariants:

- reporting file layout and schema validity
- determinism (canonical JSON formatting)
- docs/registry sync (manifest ↔ matrix)
- size limits (AGENTS.md)
- policy checks (e.g. python launcher policy)

Intent:

- Catch "paper cuts" early.
- Fail with actionable messages.

Non-goal:

- Measuring model capability.

## 2) Schema tests (tests/schema)

Schema tests validate JSON Schema files and fixtures.

Intent:

- Every schema has at least one positive fixture and one negative fixture.
- Schema changes cannot silently break downstream tooling.

Non-goal:

- End-to-end evaluation.

## 3) E2E golden cases (tests/e2e/golden)

Golden cases are *minimal deterministic repros*.

Intent:

- Small patch + `lake build` + judge.
- Exercise diagnostics parsing, PatchScope enforcement, and basic Lean compilation paths.

These are not "unit tests" and not "model eval". They are harness correctness checks.

## 4) E2E scenarios (tests/e2e/scenarios)

Scenarios test multi-step workflows:

- apply overlay
- run command
- build targets
- validate expected artifacts against schemas

Intent:

- Ensure longer workflows remain reproducible.
- Ensure artifacts are produced and well-formed.

Non-goal:

- Hiding flakiness with retries.

## 5) Stress/soak (tests/stress)

Soak runs are *deliberately long* and are sensitive to cold starts.

Common failure modes:

- `.lake/packages` cold clone of mathlib4
- `lake build` triggering mathlib cache fetch
- first-run budgets exhausted due to warm-up

Correct fixes:

- Increase budgets where justified.
- Reuse dependency caches (copy `.lake/packages`).
- Disable cache-on-update behavior via env (`MATHLIB_NO_CACHE_ON_UPDATE=1`).

Incorrect fixes:

- Adding "retry once" logic that masks real failures.
- Reclassifying failures as success.

If a soak run reports `TRIAGED/BUDGET_EXHAUSTED`, treat it as a signal that:

- budgets are too tight for the environment, or
- warm-up/caching is missing.

Fix those, then re-run.

## 6) Phase6 real-agent eval (tools/agent_eval)

Phase6 is about evaluating an agent against a fixed harness.

- `run_pack.py`: run a set of tasks (pack).
- `run_scenario.py`: run a structured multi-step scenario.

Intent:

- The runner defines the workspace and contracts.
- The agent is invoked via `--agent-cmd`.
- Graders score based on artifacts.

Key invariant:

- Required reporting artifacts must exist.
- `pins_used.json` is runner-owned to avoid punishing agents for missing bookkeeping.

