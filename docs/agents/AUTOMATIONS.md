# Automations (Codex App + Repo Harness)

This document defines how LeanAtlas uses automations without losing auditability.

## 1) Two layers (must not be confused)

- Codex App automation:
  - Owns scheduling, background execution, and inbox delivery.
  - May run in background worktrees for Git repos.
  - LeanAtlas policy: prompt commands must still execute against the source workspace path (local repo), not the worktree cwd.

- Repo automation harness:
  - `automations/registry.json` is the executable specification.
  - `tools/coordination/run_automation.py` replays deterministic steps locally and records evidence.
  - `tools/coordination/run_automation_local.py` is the Codex App-safe wrapper that forces source-workspace execution.
  - The harness validates behavior; it does not replace Codex App scheduling.

## 2) Execution model

Each automation is split into:

1. Deterministic pre-step (required)
- No LLM calls.
- Reproducible in local/CI.
- Writes outputs only under `artifacts/**` or `.cache/leanatlas/**`.

2. Advisor step (optional)
- Enabled only when `advisor.enabled=true`.
- Triggered by findings (`advisor.when=findings`) plus explicit probe signals.
- Produces auditable handoff/patch evidence.

3. Verify step (required)
- `lake lint`, `lake test`, or `lake build` as needed.

## 3) Registry rules (`automations/registry.json`)

All non-deprecated automations must define:

- `deterministic.steps[]`
- `deterministic.artifacts[]`
- `verify.steps[]`
- `tdd.profile ∈ {core, nightly}`
- `tdd.dry_run.cmd`

If an automation consumes `artifacts/telemetry`, it must first run:

```bash
python tools/bench/collect_telemetry.py --repo-root . --out-root artifacts/telemetry --clean
```

This prevents stale telemetry from leaking across runs.

## 3.1) Required active baseline (must install in Codex App)

These active automations define the operational baseline:

- `nightly_reporting_integrity` (schema/canonical JSON integrity)
- `nightly_mcp_healthcheck` (external MCP health + graceful degradation)
- `nightly_trace_mining` (attempt/run telemetry mining)
- `weekly_kb_suggestions` (skills closed loop: suggestions + regen audit + stub plan)
- `nightly_dedup_instances` (DedupGate continuous scan)
- `weekly_docpack_memory_audit` (doc-pack/memory/pin drift checks)
- `nightly_phase3_governance_audit` (promotion/gc continuous governance audit)
- `nightly_chat_feedback_deposition` (chat feedback digest + append-only ledger + traceability matrix)

Closed-loop coverage map:

- Promotion/GC continuous automation: `nightly_phase3_governance_audit`
- Skills deposition full loop: `weekly_kb_suggestions`
- Chat feedback deposition: `nightly_chat_feedback_deposition`

## 4) Local runners (`run_automation.py` + `run_automation_local.py`)

Common usage:

```bash
./.venv/bin/python tools/coordination/run_automation.py --id weekly_kb_suggestions
./.venv/bin/python tools/coordination/run_automation.py --id weekly_kb_suggestions --verify
./.venv/bin/python tools/coordination/run_automation.py --id weekly_kb_suggestions --advisor-mode auto --verify
```

Codex App prompt usage (must force local repo execution even if thread cwd is a worktree):

```bash
python /ABS/REPO/tools/coordination/run_automation_local.py --id weekly_kb_suggestions --advisor-mode auto --verify
```

Advisor modes:

- `off`: deterministic run + handoff artifact only
- `auto`: run advisor only when findings policy is satisfied
- `force`: run advisor regardless of findings policy

Even with `--advisor-mode auto|force`, scheduling still belongs to Codex App automation.

## 5) TDD and gates

Core automation gates:

- `./.venv/bin/python tests/automation/validate_registry.py`
- `./.venv/bin/python tests/automation/run_dry_runs.py`
- `./.venv/bin/python tests/contract/check_telemetry_collection_policy.py`
- `./.venv/bin/python tests/automation/check_run_automation_local.py`

Recommended full core suite:

```bash
./.venv/bin/python tests/run.py --profile core
```

## 6) External dependencies

If deterministic or verify steps depend on external tools (MCP adapters, `rg`, etc.):

- Register in `docs/setup/DEPENDENCIES.md`
- Provide install+verify docs in `docs/setup/external/*.md`
- Provide a smoke test (normally nightly tier)
