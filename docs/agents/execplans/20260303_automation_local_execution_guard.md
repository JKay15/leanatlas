---
title: Automation local-execution guard for Codex App worktree runs
owner: leanatlas-maintainer
status: done
created: 2026-03-03
---

## Purpose / Big Picture
Codex App automations are currently executed in background worktrees for Git repos. For LeanAtlas this causes runtime drift: worktrees miss the prepared `.venv` and local tool/cache context, so active automations fail even when the main workspace is healthy. This plan introduces a deterministic local-execution wrapper plus onboarding/install guardrails so automations always execute against the source workspace path. The outcome should be: app scheduler may still create a worktree thread, but the actual command runs in the local repo with repo-local Python first.

## Glossary
- source workspace: the real repo root configured in automation `cwds`.
- execution thread cwd: the cwd chosen by Codex App runtime (often worktree).
- local wrapper: repo script that forces `cwd=source workspace` and uses repo Python policy.

## Scope
In scope:
- `tools/coordination/*` local execution entrypoint.
- `tools/coordination/*` stuck-run recovery helper for app-side timeout stalls.
- onboarding verification/installation checks under `tools/onboarding/*`.
- onboarding/install docs + checklist guidance.
- automation tests validating local wrapper behavior.

Out of scope:
- Codex App scheduler internals.
- changing automation cadence/rrule set.
- schema or contract version bumps.

## Interfaces and Files
- `tools/coordination/run_automation_local.py` (new): source-workspace wrapper.
- `tools/onboarding/verify_automation_install.py`: verify local-execution prompt policy.
- `tests/automation/check_run_automation_local.py` (new): deterministic check for wrapper behavior.
- `tools/coordination/recover_stuck_automation_runs.py` (new): repair stale `IN_PROGRESS` automation runs.
- `tests/automation/check_stuck_run_recovery.py` (new): deterministic recovery contract check.
- `tests/manifest.json`: register the new test.
- `docs/agents/{ONBOARDING.md,CODEX_APP_PROMPTS.md,AUTOMATIONS.md}` and `docs/agents/templates/AUTOMATION_INSTALL_CHECKLIST.md`: update install instructions to local wrapper policy.
- `docs/agents/execplans/README.md`: index this plan.

## Milestones
1) Red test for wrapper/local policy
- Deliverables: add failing test (or check) asserting missing local wrapper/expected behavior.
- Commands:
  - `./.venv/bin/python tests/automation/check_run_automation_local.py`
- Acceptance: fails before implementation.

2) Implement local wrapper + onboarding verification
- Deliverables: add wrapper script and enforce local-execution checks in onboarding verification.
- Commands:
  - `./.venv/bin/python tests/automation/check_run_automation_local.py`
  - `./.venv/bin/python tests/automation/validate_registry.py`
- Acceptance: wrapper test and registry checks pass.

3) Update docs/install prompts + registry tests
- Deliverables: documentation switched to local wrapper pattern; manifest/test matrix/index updated.
- Commands:
  - `./.venv/bin/python tests/run.py --profile core`
- Acceptance: core profile passes.

4) Add stuck-run recovery guard + contract test
- Deliverables: recovery script + deterministic test + docs entry.
- Commands:
  - `./.venv/bin/python tests/automation/check_stuck_run_recovery.py`
  - `./.venv/bin/python tools/coordination/recover_stuck_automation_runs.py --dry-run`
  - `./.venv/bin/python tests/run.py --profile core`
- Acceptance: stale `IN_PROGRESS` rows are detected/repairable; core profile passes.

## Testing plan (TDD)
- Add a dedicated deterministic script test for local wrapper:
  - verifies generated command uses source repo root + repo-local python policy.
  - verifies wrapper forwards `--id/--advisor-mode/--verify`.
- Run targeted automation tests first, then full core profile.
- No generated run artifacts are committed.

## Decision log
- Decision: enforce local execution by wrapper script, not by hoping UI execution environment is set to local.
- Why: app may still execute in worktree; wrapper deterministically redirects execution to source workspace.
- Rejected alternative: rely on `uv run --locked` in worktree. Reason: network/offline drift and package fetch failures.

## Rollback plan
- Revert wrapper + onboarding prompt policy changes:
  - remove `tools/coordination/run_automation_local.py`
  - revert updated onboarding/docs/test entries
- Verify rollback by:
  - `./.venv/bin/python tests/run.py --profile core`

## Outcomes & retrospective
- Implemented local wrapper + onboarding/prompt policy enforcement.
- Added uv fallback in wrapper when `.venv` is unavailable.
- Added deterministic stuck-run recovery tool:
  - `tools/coordination/recover_stuck_automation_runs.py`
- Added deterministic contract test:
  - `tests/automation/check_stuck_run_recovery.py`
- Verification:
  - `./.venv/bin/python tests/automation/check_run_automation_local.py`
  - `./.venv/bin/python tests/automation/check_stuck_run_recovery.py`
  - `./.venv/bin/python tests/run.py --profile core`
