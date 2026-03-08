---
title: Enforce shared Lake requirement at test registration gate
owner: maintainer
status: done
created: 2026-03-05
---

## Purpose / Big Picture
Make test registration a hard gate for Lean shared-library policy. From now on, tests that execute Lean/Lake paths must either enforce shared Lake cache directly or delegate to approved shared-cache entrypoints. If not, registration check must fail with explicit "UNSHARED_LEAN_LIBRARY" evidence.

## Glossary
- Shared Lake policy: workspace `.lake/packages` is hydrated via `ensure_workspace_lake_packages` and avoids per-run heavy copies.
- Registration gate: `tests/contract/check_test_registry.py`.
- Delegation: wrapper tests that call approved runner entrypoints already enforcing shared policy.

## Scope
In scope:
- `tests/contract/check_test_registry.py`
- this ExecPlan

Out of scope:
- changing manifest schema
- changing runner implementation (already covered by shared-cache policy contract)

## Interfaces and Files
- `tests/contract/check_test_registry.py`
  - add Lean/Lake shared-policy registration checks
  - emit failure with code `UNSHARED_LEAN_LIBRARY`

## Milestones
1) Add registration gate logic
- Deliverables: detection for Lean-execution scripts + enforcement/delegation checks
- Acceptance: missing shared policy on such scripts yields deterministic FAIL with `UNSHARED_LEAN_LIBRARY`

2) Validate contracts
- Commands:
  - `uv run --locked python tests/contract/check_test_registry.py`
  - `uv run --locked python tests/contract/check_shared_cache_policy.py`
- Acceptance: both pass in current tree

## Testing plan (TDD)
- Add/adjust gate logic, then run `check_test_registry` as the first validation loop to catch false positives/negatives on current registered scripts.
- Re-run shared-cache policy contract to ensure consistency.

## Decision log
- Keep schema unchanged; enforce at contract layer for fast rollout and deterministic messaging.
- Use approved entrypoint delegation model to avoid forcing wrapper scripts to duplicate cache code.

## Rollback plan
- Revert `tests/contract/check_test_registry.py`.
- Run `uv run --locked python tests/contract/check_test_registry.py` to confirm old behavior.

## Outcomes & retrospective (fill when done)
- Implemented `check_test_registry` hard gate for shared Lean/Lake policy:
  - Added deterministic detection of Lean/Lake execution paths (literal/variable/shell-call patterns).
  - Added compliance checks: direct `ensure_workspace_lake_packages` function call OR delegation via approved runner invocation patterns.
  - Added explicit failure code `UNSHARED_LEAN_LIBRARY`.
  - Added non-Python script guard: Lean/Lake-marked non-Python tests cannot bypass registration gate.
- Validation commands:
  - `uv run --locked python tests/contract/check_test_registry.py` -> PASS
  - `uv run --locked python tests/contract/check_shared_cache_policy.py` -> PASS
  - `uv run --locked python tests/contract/check_manifest_completeness.py` -> PASS
