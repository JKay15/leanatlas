---
title: Repo-wide agent-provider rollout (remove executable Codex-only choke points)
owner: Codex (local workspace)
status: done
created: 2026-03-04
---

## Purpose / Big Picture
v0/v0.2 introduced provider/profile abstraction for Phase6 runners and automation advisor execution, but several operational entry points still require a direct Codex-only command string (`LEANATLAS_REAL_AGENT_CMD`). This plan removes those remaining executable choke points by allowing real-agent onboarding and nightly checks to run through provider/profile selection as first-class inputs (with command-string backward compatibility). The goal is not branding rewrite; it is runtime interface unification so future platform switching does not require scattered code edits.

## Glossary
- Real-agent config: onboarding/runtime inputs used by nightly real-agent checks.
- Provider/profile path: selecting agent execution via `agent_provider` and optional `agent_profile` (resolved by `tools/agent_eval/agent_provider.py`).
- Legacy command path: direct shell command via `LEANATLAS_REAL_AGENT_CMD`.

## Scope
In scope:
- Runtime scripts:
  - `scripts/bootstrap.sh`
  - `scripts/doctor.sh`
- Nightly real-agent tests:
  - `tests/agent_eval/exec_pack_real_agent_nightly.py`
  - `tests/agent_eval/exec_scenario_real_agent_nightly.py`
- Setup/docs/tests affected by real-agent contract:
  - `docs/setup/QUICKSTART.md`
  - `tools/tests/generate_test_env_inventory.py`
  - `docs/setup/TEST_ENV_INVENTORY.md`
  - contract checks that validate setup docs or script policy.
- Codex coupling inventory task doc (code/text split) for follow-up migration batches.

Out of scope:
- Rewriting all historical docs that mention Codex conceptually.
- Changing automation scheduler ownership or Codex App semantics.
- Removing legacy `LEANATLAS_REAL_AGENT_CMD` support.

## Interfaces and Files
- `scripts/bootstrap.sh` / `scripts/doctor.sh`
  - accept and persist real-agent config with precedence:
    1) explicit command (`LEANATLAS_REAL_AGENT_CMD`)
    2) provider/profile (`LEANATLAS_REAL_AGENT_PROVIDER`, `LEANATLAS_REAL_AGENT_PROFILE`)
  - default interactive provider remains explicit (`codex_cli`) unless user chooses otherwise.
- `tests/agent_eval/exec_*_real_agent_nightly.py`
  - resolve invocation by shared resolver from env (provider/profile/cmd).
- `tools/tests/generate_test_env_inventory.py`
  - include new env vars category and command evidence logic.
- `docs/review/20260304_codex_coupling_inventory.md`
  - exhaustive, grouped list of Codex references for phased migration.

## Milestones
1) Planning + inventory
- Deliverables:
  - this ExecPlan
  - codex coupling inventory document (code/text split)
- Acceptance:
  - inventory clearly marks executable coupling points vs narrative mentions.

2) TDD first
- Deliverables:
  - update/add tests to require provider/profile-capable real-agent paths.
- Commands:
  - targeted contract/tests for setup scripts and nightly real-agent runners.
- Acceptance:
  - tests fail before runtime implementation.

3) Runtime implementation
- Deliverables:
  - bootstrap/doctor real-agent config enhancements
  - nightly runner resolution via shared provider resolver
- Acceptance:
  - targeted tests pass; legacy command path still works.

4) Docs + deterministic inventory sync
- Deliverables:
  - update quickstart and generated env inventory
- Commands:
  - `uv run --locked python tools/tests/generate_test_env_inventory.py --write`
  - determinism/doc checks
- Acceptance:
  - docs contracts and canonical checks pass.

5) Regression verification
- Commands:
  - `uv run --locked python tests/run.py --profile core`
- Acceptance:
  - core profile passes.

## Testing plan (TDD)
- Update tests first for:
  - real-agent configuration docs/contract messaging (provider/profile + cmd compatibility)
  - nightly real-agent scripts accepting provider/profile env path
  - setup inventory generation coverage for new env vars
- Keep legacy compatibility assertions in place.

## Decision log
- Keep `LEANATLAS_REAL_AGENT_CMD` as backward-compatible override.
- Add provider/profile envs rather than replacing command env immediately to minimize migration friction.
- Use existing shared resolver (`tools/agent_eval/agent_provider.py`) to avoid duplicated command synthesis logic.

## Rollback plan
- Revert changed files in this plan scope.
- Re-run targeted tests and `core` to verify rollback to pre-rollout behavior.

## Outcomes & retrospective (fill when done)
- Completed:
  - Added repo-wide migration task ledger (code/text split):
    - `docs/review/20260304_codex_coupling_inventory.md`
  - Added provider contract test for nightly real-agent entrypoints:
    - `tests/agent_eval/check_real_agent_provider_contract.py`
    - registered in `tests/manifest.json` (`profile=core`)
  - Upgraded real-agent onboarding scripts to support provider/profile + legacy command:
    - `scripts/bootstrap.sh`
    - `scripts/doctor.sh`
    - supported envs:
      - `LEANATLAS_REAL_AGENT_PROVIDER`
      - `LEANATLAS_REAL_AGENT_PROFILE` (optional)
      - `LEANATLAS_REAL_AGENT_CMD` (legacy override)
  - Upgraded nightly real-agent runners to use shared resolver and provider/profile args:
    - `tests/agent_eval/exec_pack_real_agent_nightly.py`
    - `tests/agent_eval/exec_scenario_real_agent_nightly.py`
  - Updated setup/docs/tooling for new env contract:
    - `docs/setup/QUICKSTART.md`
    - `tools/tests/generate_test_env_inventory.py`
    - regenerated `docs/setup/TEST_ENV_INVENTORY.md`
    - regenerated `docs/testing/TEST_MATRIX.md`
  - Updated key usage docs from command-only examples to provider-first examples:
    - `docs/agents/CODEX_APP_PROMPTS.md`
    - `docs/agents/phase6/PHASE6_USAGE.md`
    - `tests/agent_eval/README.md`
    - `automations/README.md`

- TDD evidence (red -> green):
  - Red (before implementation):
    - `tests/contract/check_bootstrap_venv_fallback_policy.py`
    - `tests/contract/check_doctor_python_preference_policy.py`
    - `tests/contract/check_setup_docs.py`
    - `tests/agent_eval/check_real_agent_provider_contract.py`
  - Green (after implementation): all above pass.

- Verification:
  - Targeted:
    - `uv run --locked python tests/agent_eval/check_real_agent_provider_contract.py` (PASS)
    - `uv run --locked python tests/contract/check_bootstrap_venv_fallback_policy.py` (PASS)
    - `uv run --locked python tests/contract/check_doctor_python_preference_policy.py` (PASS)
    - `uv run --locked python tests/contract/check_setup_docs.py` (PASS)
    - `uv run --locked python tests/contract/check_test_env_inventory_up_to_date.py` (PASS)
    - `uv run --locked python tests/contract/check_test_matrix_up_to_date.py` (PASS)
    - `uv run --locked python tests/contract/check_test_registry.py` (PASS)
    - `uv run --locked python tests/schema/validate_schemas.py` (PASS)
    - `uv run --locked python tests/automation/check_run_automation_local.py` (PASS)
    - `uv run --locked python tests/determinism/check_canonical_json.py` (PASS)
  - Full:
    - `uv run --locked python tests/run.py --profile core` (PASS)

- Notes:
  - Compatibility preserved: legacy `LEANATLAS_REAL_AGENT_CMD` continues to work.
  - Migration path is now consistent with v0.2 resolver across onboarding, nightly real-agent tests, and docs examples.
