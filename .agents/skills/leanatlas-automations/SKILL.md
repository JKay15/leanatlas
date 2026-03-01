---
name: leanatlas-automations
description: "Run LeanAtlas background maintenance automations safely: validate the registry, execute deterministic pre-steps, archive artifacts, and (only if there are findings) prepare a minimal verified patch."
---

## Use when
- The task is explicitly about **Codex Automations** (scheduling/maintenance/inbox triage) or running `tools/coordination/automation_nightly.py`.
- You need to validate or change `automations/registry.json` and ensure deterministic pre-steps still pass.

## Don't use when
- You are proving a new math problem under `Problems/**` (use `leanatlas-operator-proof-loop`).
- You are changing business rules for GC/Dedup/Promotion (use the dedicated Phase3 skills + ExecPlans).

## Outputs
- `artifacts/**` findings (logs, deltas, stub plans)
- Minimal PR-ready patch (only when deterministic evidence supports it)

## Must-run checks
- `uv run --locked python tests/automation/validate_registry.py`
- `uv run --locked python tests/automation/run_dry_runs.py`

## Codex Automations: practical notes
- Before you schedule an automation, test the prompt manually in a regular thread first.
- In Git repositories, Codex automations run in background worktrees. Don’t assume your local checkout is the workspace.
- You can force-trigger this skill from an automation by including `$leanatlas-automations` in the automation prompt.

## Hard constraints
- Never bypass deterministic pre-steps.
- Never edit outside the workspace/worktree.
- If you are in OPERATOR mode, do **not** touch system files; output TRIAGED with a maintainer plan.

## Standard playbook

### 1) Read-first
- `docs/contracts/AUTOMATION_CONTRACT.md`
- `automations/registry.json` (find the target automation id)

### 2) Deterministic pre-steps (no Codex needed)
Run deterministic steps exactly as specified in the registry.

Useful entrypoints:
- Validate registry structure (spec-level):
  - `python tests/automation/validate_registry.py`
- Dry-run a single automation (deterministic steps only):
  - `python tests/automation/dry_run_single.py --id <automation_id>`
- Dry-run all ACTIVE + core-tier automations:
  - `python tests/automation/run_dry_runs.py`
- Nightly-style deterministic execution + per-run archival:
  - `python tools/coordination/automation_nightly.py --cadence nightly`

Other useful platform tools:
- Collect telemetry into unified input root (recommended before trace mining / KB suggestions):
  - `python tools/bench/collect_telemetry.py --repo-root . --out-root artifacts/telemetry --clean`
- Compare two bench reports (today vs yesterday style):
  - `python tools/bench/compare_bench_reports.py --old <old.json> --new <new.json> --out <delta.json> --summary-md <delta.md>`
- Generate skill stub/coverage plan when new commands appear:
  - `python tools/coordination/skills_stubgen.py --repo-root . --out artifacts/skills_regen/stub_plan.json`

Write findings only under `artifacts/**`.

### 3) If there are findings
- Propose the smallest possible patch.
- Run verification commands from the registry (`lake lint`, `lake test`, etc.).
- Ensure the repo is clean (no leftover tracked changes beyond the patch).

### 4) Output
- A short summary referencing findings artifact paths.
- A clear PR-ready change list.
