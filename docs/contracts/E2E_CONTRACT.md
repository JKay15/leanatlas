# E2E_CONTRACT v0.1 (Phase 2)

This contract defines the **deterministic E2E golden case suite**.

Goals:
- Make the small-loop behavior testable without relying on LLM "intelligence".
- Ensure TRIAGED/SUCCESS exits are auditable and stable.
- Provide a place to grow coverage over time (smoke/core/nightly).

Non-goals:
- Benchmarking speed (handled in later perf tests).
- Full mathlib correctness in early Phase 2 scaffolds (runner evolves over phases).

---

## 1) Directory layout

Each case lives under:

`tests/e2e/golden/<case_id>/`

Required files:
- `case.yaml` (case metadata; validated by schema)


Budget overrides (optional):
- `execution.budgets.limits` may override default run limits for this case.
  - Example: `{ max_attempts: 1 }` to force a `BUDGET_EXHAUSTED` stop before patches are applied.
  - Supported keys: `max_attempts`, `max_steps`, `max_external_queries`, `max_wall_time_ms`.

Tooling failure simulation (optional):
- `execution.simulate_tooling_failure: true` forces the runner to treat retrieval as failed and to emit a deterministic `TOOLING_FAILURE` TRIAGE.
  - This is used to test tool/infra failures without depending on a real MCP server.

Optional:
- `patches/` (deterministic patch sequence for fixable cases)
- `fixture/` (a minimal problem workspace template to copy into a temp workdir)

---

## 2) Case metadata (`case.yaml`)

A case MUST declare:
- `id`: case id (must equal folder name)
- `tier`: `smoke | core | nightly`
- `expected`:
  - `final_status`: `SUCCESS | TRIAGED`
  - when TRIAGED: `triage_level` + `category.family` + `category.code` + `judge_reason_code`
- `coverage_tags`: list of tags, including at least one `family:<FAMILY>` tag.

If the case is fixable, it SHOULD also declare:
- `patch_sequence`: ordered list of patch filenames under `patches/`.

---

## 3) Coverage requirements (Phase 2 baseline)

Coverage is enforced by a deterministic validator test (core tier):

- In `smoke`+`core`, there MUST be at least one case for each family:
  - IMPORT, NAME, TYPE, TACTIC, ASSUMPTION, DEFINITION, STATEMENT, TOOLING, BUDGET
- `nightly` may add extended/perf/tooling regression cases.

---

## 4) Determinism rules

- E2E tests MUST NOT depend on LLM randomness.
- Fixable cases use deterministic patches (static text files).
- TRIAGED cases validate classification and evidence references (diagnostic ids, stage, trace step indices) where applicable.

---

## 5) Future integration

Later phases may add:
- a real runner that copies `fixture/` into a sandbox workdir and invokes `lake build`
- trace grading / scoring on the AttemptLog (offline)
- performance budgets and import-graph regression checks


## Executable cases (Phase 2.3)

A case may optionally be *executable* on a machine with Lean/Lake and (optionally) mathlib available.

If `execution.enabled: true`, the case directory MUST contain:

- `fixture/` (overlay applied onto `tests/e2e/fixture_root/`)
  - `Problems/<case_id>/Spec.lean`
  - `Problems/<case_id>/Proof.lean`
  - `Problems/<case_id>/Cache.lean`
  - `Problems/<case_id>/Scratch.lean`

Optional:

- `patches/<nnn>/...` overlay directories referenced by `patch_sequence`, applied in order.

The e2e runner builds the module:

- default `build_target = Problems.<case_id>.Proof`
- default `main_decl = Problems.<case_id>.main`

A case may override these via:

```yaml
execution:
  enabled: true
  build_target: "Problems.my_case.Proof"
  main_decl: "Problems.my_case.main"
```

All outputs are written under `artifacts/e2e/<case_id>/<run_id>/...` and are ignored by git.

