# ExecPlan: Hard Convergence Pack (Automation + Telemetry + English Gate)

Date: 2026-02-28  
Mode: MAINTAINER  
Owner: Codex (local workspace)

## 1) Scope

This plan lands one bounded convergence patch set:

1. Fix automation contract drift to `tdd.profile`.
2. Add deterministic telemetry collection before telemetry-mining automations.
3. Add advisor execution switch and findings probe semantics to local automation harness.
4. Add an English-only contract gate to prevent mixed-language regressions.

## 2) Terms

- Codex App automation: scheduler + background run + inbox behavior in Codex UI.
- Repo automation harness: local deterministic executor (`tools/coordination/run_automation.py`) used for verification.
- Findings probe: deterministic JSON-based signal that decides whether advisor should execute in auto mode.

## 3) Files to change

- `automations/registry.json`
- `tools/coordination/run_automation.py`
- `tests/automation/validate_registry.py`
- `tests/automation/run_dry_runs.py`
- `tools/bench/collect_telemetry.py` (new)
- `tests/contract/check_telemetry_collection_policy.py` (new)
- `tests/contract/check_english_only_policy.py` (new)
- `docs/contracts/AUTOMATION_CONTRACT.md`
- `docs/contracts/BENCH_CONTRACT.md`
- `docs/contracts/SKILLS_GROWTH_CONTRACT.md`
- `docs/agents/AUTOMATIONS.md`
- `tools/capabilities/phase5.yaml`
- `.agents/skills/leanatlas-automations/SKILL.md`
- `.agents/skills/leanatlas-automations/references/coverage.yaml`
- `tests/manifest.json`
- `docs/testing/TEST_MATRIX.md` (regenerated)
- `docs/navigation/FILE_INDEX.md` (regenerated)

## 4) Acceptance checks

Run:

```bash
./.venv/bin/python tests/automation/validate_registry.py
./.venv/bin/python tests/automation/run_dry_runs.py
./.venv/bin/python tests/contract/check_telemetry_collection_policy.py
./.venv/bin/python tests/contract/check_english_only_policy.py
./.venv/bin/python tests/contract/check_capability_manifests.py
./.venv/bin/python tests/contract/check_test_registry.py
./.venv/bin/python tests/contract/check_test_matrix_up_to_date.py
./.venv/bin/python tests/contract/check_file_index_reachability.py
./.venv/bin/python tests/run.py --profile core
```

## 5) Rollback points

- Revert only telemetry-related changes:
  - `tools/bench/collect_telemetry.py`
  - `tests/contract/check_telemetry_collection_policy.py`
  - related registry step insertions.
- Revert only advisor execution changes:
  - `tools/coordination/run_automation.py`
  - registry `advisor.probe` fields.
- Revert only language gate:
  - `tests/contract/check_english_only_policy.py`
  - manifest entry + matrix line.
