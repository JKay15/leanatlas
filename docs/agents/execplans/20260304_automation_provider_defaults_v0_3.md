---
title: Automation provider defaults v0.3 (registry-first advisor execution)
owner: Codex (local workspace)
status: done
created: 2026-03-04
---

## Purpose / Big Picture
v0.2 added provider/profile bridge for automation advisor execution, but active automations still require manual CLI flags (`--agent-provider`) in many operator paths. This plan shifts advisor execution defaults into `automations/registry.json` so local wrapper calls can stay minimal and deterministic. We also add dry-run visibility of selected/default provider resolution to improve auditability.

## Glossary
- Advisor executor config: one of `advisor.exec_cmd` (legacy) or provider/profile (`advisor.agent_provider`, `advisor.agent_profile`).
- Registry-first default: execution config declared in `automations/registry.json` and reused by runner without extra CLI args.

## Scope
In scope:
- `automations/registry.json` advisor defaults for active enabled automations.
- `tests/automation/validate_registry.py` hardening for advisor executor requirements.
- `tools/coordination/run_automation.py` dry-run visibility for advisor provider/profile resolution.
- New/updated automation tests and manifest registration.
- Contract/doc updates tied to automation execution semantics.

Out of scope:
- Changing Codex App scheduler ownership.
- Removing legacy `advisor.exec_cmd` or CLI override flags.
- Rewriting broad branding docs.

## Interfaces and Files
- Registry:
  - `automations/registry.json`
- Validation:
  - `tests/automation/validate_registry.py`
- Runner:
  - `tools/coordination/run_automation.py`
- Tests:
  - `tests/automation/check_run_automation_provider_visibility.py` (new)
  - `tests/manifest.json` (register new test)
- Docs:
  - `docs/contracts/AUTOMATION_CONTRACT.md`
  - `docs/agents/AUTOMATIONS.md`

## Milestones
1) TDD first
- Add test for dry-run provider visibility.
- Harden registry validator to require executable advisor config for enabled advisors.
- Expect failing tests before implementation.

2) Implement registry-first defaults
- Add `advisor.agent_provider` to active enabled automations.
- Keep backward compatibility and deterministic structure.

3) Implement dry-run visibility
- `run_automation.py --dry-run` prints selected/default advisor provider/profile + source (CLI/registry).

4) Verify + docs
- Run targeted automation tests/contracts.
- Run `tests/run.py --profile core`.
- Update contracts/docs accordingly.

## Testing plan (TDD)
- Targeted:
  - `uv run --locked python tests/automation/validate_registry.py`
  - `uv run --locked python tests/automation/check_run_automation_provider_visibility.py`
  - `uv run --locked python tests/automation/check_run_automation_local.py`
- Regression:
  - `uv run --locked python tests/contract/check_test_registry.py`
  - `uv run --locked python tests/contract/check_test_matrix_up_to_date.py`
  - `uv run --locked python tests/run.py --profile core`

## Decision log
- Keep `advisor.exec_cmd` path valid, but require enabled advisors to declare an executable default (`exec_cmd` or provider/profile).
- Prefer registry defaults over prompt-time CLI flags for reproducible automation behavior.

## Rollback plan
- Revert files listed in scope.
- Re-run targeted tests above to confirm pre-v0.3 behavior.

## Outcomes & retrospective (fill when done)
- Completed:
  - Added registry/provider visibility TDD:
    - `tests/automation/check_run_automation_provider_visibility.py` (new)
    - `tests/automation/validate_registry.py` hardening for enabled advisor executor defaults
    - registered test in `tests/manifest.json`
  - Implemented registry-first advisor defaults:
    - populated `advisor.agent_provider: "codex_cli"` for all active `advisor.enabled=true` automations in `automations/registry.json`
  - Implemented dry-run advisor selection visibility in runner:
    - `tools/coordination/run_automation.py`
    - now reports selected provider/profile and source (`registry` vs `cli`) in `--dry-run`
  - Contract/schema/docs updates:
    - `docs/schemas/AutomationRegistry.schema.json` (enabled-advisor executor requirement via `if/then`)
    - `docs/contracts/AUTOMATION_CONTRACT.md`
    - `docs/agents/AUTOMATIONS.md`
    - provider-first wording updates in:
      - `docs/testing/TEST_INTENTS.md`
      - `docs/agents/phase6/MENTOR_KEYWORDS_TASKPACK.md`
      - `docs/agents/EVAL_PROBLEM_PACK_GUIDE.md`
      - `docs/agents/MAINTAINER_INIT_TASKS.md`
  - Regenerated matrix:
    - `docs/testing/TEST_MATRIX.md`

- TDD evidence (red -> green):
  - Red:
    - `uv run --locked python tests/automation/validate_registry.py`
    - `uv run --locked python tests/automation/check_run_automation_provider_visibility.py`
  - Green:
    - both tests pass after registry + runner updates.

- Verification:
  - Targeted:
    - `uv run --locked python tests/automation/validate_registry.py` (PASS)
    - `uv run --locked python tests/automation/check_run_automation_provider_visibility.py` (PASS)
    - `uv run --locked python tests/automation/check_run_automation_local.py` (PASS)
    - `uv run --locked python tests/schema/validate_schemas.py` (PASS)
    - `uv run --locked python tests/contract/check_test_registry.py` (PASS)
    - `uv run --locked python tests/contract/check_test_matrix_up_to_date.py` (PASS)
    - `uv run --locked python tests/determinism/check_canonical_json.py` (PASS)
  - Full:
    - `uv run --locked python tests/run.py --profile core` (PASS)

- Notes:
  - CLI override behavior remains intact (`--agent-provider`, `--agent-profile`).
  - Registry defaults now eliminate routine per-run provider flags for active advisor-enabled automations.
