# AUTOMATION_CONTRACT

Purpose: make “Codex background automation tasks” into auditable, reproducible, TDD-backed engineering components.
This contract constrains: registry structure, artifact locations, and testing gates.

## 1) Definitions (must be executable)
- **Automation**: a scheduled/triggered workflow that runs without interactive user input.
- **Deterministic pre-step**: steps that do not rely on an LLM (scripts/Lean executables/static checks). Must be reproducible in CI.
- **Advisor step**: may use Codex to generate a patch/PR, but must be constrained and verified.
- **Dry-run (TDD)**: run only the deterministic pre-step (no Codex calls) to prevent automation rot.

## 2) Single source of truth
- Automation specs live in `automations/registry.json`.
- `docs/agents/AUTOMATIONS.md` explains how these map to Codex App Automations / Codex CLI.
- `tools/coordination/run_automation.py` is the local harness for deterministic execution and advisor handoff semantics.
  It is not a scheduler replacement; Codex App UI owns scheduling/inbox behavior.

## 3) Mandatory structure (all non-deprecated automations)
For registry entries with `status ∈ {active, planned}`:

### 3.1 Deterministic pre-step (required)
- At least 1 deterministic step.
- Each step must specify: `name`, `cmd`.
- Step artifacts must be written under `artifacts/**` or `.cache/leanatlas/**` (must be gitignored).
- If an automation consumes `artifacts/telemetry`, it must run `tools/bench/collect_telemetry.py --clean`
  before consuming steps to avoid stale telemetry contamination.

### 3.2 Verification (required)
- Must include at least one verification command: `lake lint` or `lake test` (and `lake build` when needed).
- Any Advisor-generated patch must pass verification in the same worktree.

### 3.3 TDD (required)
- Must provide `tdd.profile` (`core` or `nightly`).
- Must provide `tdd.dry_run.cmd` (runs only deterministic pre-step; no Codex).
- `core` profile must be fast, deterministic, and offline-friendly.
- `nightly` profile may be heavier (Lean+mathlib/MCP) and is used for realistic smoke/soak.

TDD ensures the framework + deterministic core never silently rots. The Advisor is an accelerator, not the verifier.

## 4) Active vs Planned
- `status=active`: relied upon long-term; deterministic steps must keep working.
- `status=planned`: spec agreed; implementation may still be catching up; still must dry-run (at least the deterministic skeleton).

## 5) Advisor step hard constraints
If `advisor.enabled = true`:
- Advisor triggers only when deterministic steps produced **findings** (`advisor.when = findings`).
- `run_automation.py --advisor-mode auto` must use explicit findings probes (`advisor.probe`) or deterministic-failure signals.
- Enabled advisors must declare a default local executor in registry:
  - provider/profile bridge (`advisor.agent_provider` and optional `advisor.agent_profile`) as default path, or
  - `advisor.exec_cmd` as legacy fallback.
- Advisor execution may be supplied in two ways:
  - direct `advisor.exec_cmd` (legacy)
  - provider/profile bridge (`advisor.agent_provider` / `advisor.agent_profile`, or CLI `--agent-provider/--agent-profile`)
- CLI flags may override registry defaults, but registry defaults should be sufficient for reproducible local runs.
- Advisor must obey PatchScope (OPERATOR/MAINTAINER rules).
- Advisor must write auditable artifacts:
  - patch/PR
  - findings report (and/or RunReport/AttemptLog)
- Before finishing, Advisor must run verification commands and record results in artifacts.

## 6) External dependencies
If deterministic steps or verification rely on external tools (MCP servers, `rg`, `sqlite`, etc.):
- register in `docs/setup/DEPENDENCIES.md`
- provide install/verify doc: `docs/setup/external/<name>.md`
- provide a smoke check (prefer nightly profile)
