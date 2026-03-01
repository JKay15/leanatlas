# E2E_SCENARIO_CONTRACT v0.1 (Phase 2.4)

This contract defines **sequential E2E scenarios** and **stress/soak** style tests.

Why scenarios exist
- Single-case E2E tests validate "one problem in isolation".
- Real usage is **serial** and **stateful**:
  - many problems live in the same repo over time
  - fixes/promotion can change shared modules (Toolbox/Seeds) and cause regressions
  - repeated runs can reveal flakiness, state leaks, and performance cliffs

Goals
- Provide deterministic, replayable sequences that can catch:
  1) "fix A, then B breaks" (cross-problem interference)
  2) "promotion/regeneration breaks previous proofs" (regression)
  3) "after many runs, things degrade" (soak/stress)

Non-goals
- Proving mathematical difficulty: scenarios are engineering tests.
- Running in minimal CI: scenario execution typically requires local Lean/Lake+mathlib.

Directory layout
- `tests/e2e/scenarios/<scenario_id>/scenario.yaml`
- optional overlays under:
  - `tests/e2e/scenarios/<scenario_id>/overlays/<name>/...`

Schema
- `docs/schemas/E2EScenario.schema.json`

Step kinds (minimal set)
1) `run_case`
   - Runs an existing golden case from `tests/e2e/golden/<case_id>/`.
   - Applies its `fixture/` and `patch_sequence` (if any).
   - Executes `lake build <target>` inside the shared workspace.
   - Produces standard reports under `artifacts/e2e_scenarios/...`.

2) `apply_overlay`
   - Copies an overlay directory into the shared workspace.
   - Intended for MAINTAINER-style steps (e.g., simulate promotion/regeneration).
   - May touch shared modules (e.g., `LeanAtlas/**`).

3) `lake_build`
   - Runs `lake build <target>` as a regression guard.
   - Recommended targets:
     - `Problems` (build the whole Problems library)
     - `LeanAtlas` (build shared library)
     - a specific module path

4) `clean`
   - Removes run outputs under `Problems/**/Reports/**` and `artifacts/**` in the workspace.
   - Used to test cleanup/idempotence.

Expectations
- A `run_case` step may optionally include `expect` overrides, e.g. expecting TRIAGED after a regression.
- `lake_build` may specify `expect_rc` (default 0).

Execution
- `tests/e2e/run_scenarios.py` executes scenarios locally.
- Validation (schema + references) is gated by `tests/e2e/validate_scenarios.py`.

Stress tests
- Heavy soak tests are kept as **manual/nightly** scripts (not core CI),
  typically under `tests/stress/`.
