---
title: Enforce generated-doc guardrails across Codex and human commits
owner: LeanAtlas maintainers
status: done
created: 2026-03-04
---

## Purpose / Big Picture
Nightly automations failed because generated docs drifted from their deterministic sources and the drift was only detected late in verify steps. This plan introduces earlier, layered guardrails so generated docs are refreshed and checked before changes reach `main`. The target docs are `docs/navigation/FILE_INDEX.md` and `docs/testing/TEST_MATRIX.md`. We add local pre-commit automation, a core contract test, and CI checks so both Codex and human contributors are constrained by the same rules. We also restore a previously developed newline-canonicalization fix that was not present on `main`.

## Glossary
- Generated docs: docs produced deterministically from source-of-truth files/scripts.
- Guardrail: an automated check/hook that blocks inconsistent states.
- Contract test: deterministic test under `tests/contract` that enforces repository policy.
- Drift: any byte-level mismatch between generated output and committed doc snapshots.

## Scope
In scope:
- `tools/**`, `tests/**`, `docs/**`, `.pre-commit-config.yaml`, `.github/workflows/**`, `AGENTS.md`
- Generated-doc enforcement for FILE_INDEX + TEST_MATRIX
- Restore newline canonicalization fix commit onto `main`

Out of scope:
- Changing automation business logic beyond guardrail integration
- Adding new external dependencies
- Refactoring unrelated test harness behavior

## Interfaces and Files
- `tools/docs/generate_file_index.py`: deterministic FILE_INDEX generator.
- `tools/tests/generate_test_matrix.py`: deterministic TEST_MATRIX generator.
- `tests/contract/check_file_index_reachability.py`: FILE_INDEX contract check.
- `tests/contract/check_test_matrix_up_to_date.py`: TEST_MATRIX contract check.
- `.pre-commit-config.yaml`: local commit/push hooks.
- `.github/workflows/generated-doc-guardrails.yml`: CI check for generated docs.
- `AGENTS.md`: repository hard rule text for contributors/Codex.
- `tests/manifest.json`: source-of-truth test registry; must include any new contract test.

## Milestones
### M1: Add failing contract test (TDD)
Deliverables:
- Add `tests/contract/check_generated_docs_guardrails.py`
- Register test in `tests/manifest.json`
Commands:
- `./.venv/bin/python tests/contract/check_generated_docs_guardrails.py`
Acceptance:
- Fails initially because required guardrails are missing/incomplete.

### M2: Implement guardrails
Deliverables:
- Update `.pre-commit-config.yaml` to auto-regenerate and then verify generated docs.
- Add `.github/workflows/generated-doc-guardrails.yml` running deterministic checks.
- Update `AGENTS.md` hard-rule wording to explicitly cover FILE_INDEX + TEST_MATRIX triggers.
- Restore `185585b` newline canonicalization fix onto `main`.
Commands:
- `git cherry-pick 185585b`
- `./.venv/bin/python tests/contract/check_generated_docs_guardrails.py`
Acceptance:
- New contract test passes.
- Generators produce canonical output and no false newline drift.

### M3: Verify and synchronize generated docs
Deliverables:
- Regenerated `docs/navigation/FILE_INDEX.md` and `docs/testing/TEST_MATRIX.md`.
- Updated execplan index list.
Commands:
- `./.venv/bin/python tools/docs/generate_file_index.py --write`
- `./.venv/bin/python tools/tests/generate_test_matrix.py --write`
- `./.venv/bin/python tests/contract/check_file_index_reachability.py`
- `./.venv/bin/python tests/contract/check_test_matrix_up_to_date.py`
- `./.venv/bin/python tests/run.py --profile core`
- `lake build`
Acceptance:
- Core profile passes, lake build passes, and working tree is clean except intentional patch.

## Testing plan (TDD)
- New test: `tests/contract/check_generated_docs_guardrails.py`
  - Asserts pre-commit config has generation + verification hooks.
  - Asserts CI workflow exists and runs both contract checks.
  - Asserts root `AGENTS.md` contains explicit generated-doc hard rule text.
- Regression checks:
  - `check_file_index_reachability.py`
  - `check_test_matrix_up_to_date.py`
- Full fast gate:
  - `tests/run.py --profile core`

## Decision log
- Chosen layered enforcement (local hook + CI + contract test + AGENTS hard rule) to avoid single-point failure.
- Chosen deterministic, dependency-free checks in CI to keep gate reliable.
- Chosen to cherry-pick canonicalization fix instead of reimplementing, preserving prior tested behavior.

## Rollback plan
- Revert commit(s) touching:
  - `.pre-commit-config.yaml`
  - `.github/workflows/generated-doc-guardrails.yml`
  - `tests/contract/check_generated_docs_guardrails.py`
  - `AGENTS.md`
  - any cherry-picked canonicalization changes
- Re-run:
  - `./.venv/bin/python tests/run.py --profile core`
  - `lake build`
- Confirm `git status --porcelain` clean and main behavior restored.

## Outcomes & retrospective (fill when done)
- Implemented:
  - Added contract test `tests/contract/check_generated_docs_guardrails.py`.
  - Added local pre-commit hooks to regenerate and verify FILE_INDEX/TEST_MATRIX.
  - Added CI workflow `.github/workflows/generated-doc-guardrails.yml`.
  - Updated root `AGENTS.md` hard rule with explicit TEST_MATRIX regeneration triggers.
  - Restored canonical newline fix by cherry-picking `185585b` onto `main`.
- Verification summary:
  - `./.venv/bin/python tests/contract/check_generated_docs_guardrails.py` -> PASS
  - `./.venv/bin/python tests/contract/check_file_index_reachability.py` -> PASS
  - `./.venv/bin/python tests/contract/check_test_matrix_up_to_date.py` -> PASS
  - `./.venv/bin/python tests/run.py --profile core` -> PASS
  - `lake build` -> PASS
  - `./.venv/bin/python tests/run.py --profile nightly` -> PASS (real-agent checks SKIP when env vars absent)
- Follow-ups:
  - Configure branch protection to require `generated-doc-guardrails` CI status on `main`.
