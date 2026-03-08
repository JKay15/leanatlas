---
title: Harden test registry shared-Lake gate against bypasses
owner: maintainer
status: done
created: 2026-03-05
---

## Purpose / Big Picture
Close known bypasses in the test registration gate so "registered but unshared Lean/Lake execution" always fails deterministically. The previous gate already checked many direct patterns, but review found gaps (`os.popen`, `subprocess` star import, spoofed delegation, spoofed ensure function). This plan hardens detection and provenance checks while keeping deterministic behavior and existing workflow compatibility.

## Glossary
- Shared Lake policy: Lean/Lake execution must route through shared package hydration via `ensure_workspace_lake_packages`.
- Registration gate: `tests/contract/check_test_registry.py`.
- Bypass: a script that executes Lean/Lake commands but still passes registration checks without real shared-cache enforcement.

## Scope
In scope:
- `tests/contract/check_test_registry.py`
- this ExecPlan

Out of scope:
- modifying runner implementations (`tests/e2e/*`, `tests/stress/*`, `tools/agent_eval/*`)
- schema changes for `tests/manifest.json`

## Interfaces and Files
- `tests/contract/check_test_registry.py`
  - add explicit self-tests for known bypass patterns (TDD)
  - harden execution API detection (`os.popen`, star-import subprocess forms)
  - harden ensure provenance checks (must be imported from shared-cache module)
  - harden delegation detection (AST call-level, not comment/string regex)

## Milestones
1) Add deterministic self-tests first (red)
- Deliverables: `_run_self_tests()` + fixtures for bypass patterns
- Acceptance: command `uv run --locked python tests/contract/check_test_registry.py --self-test` fails before hardening

2) Implement hardening (green)
- Deliverables: updated detection/provenance logic
- Acceptance: same self-test command passes; each previous bypass is blocked

3) Verify contract and profiles
- Commands:
  - `uv run --locked python tests/contract/check_test_registry.py --self-test`
  - `uv run --locked python tests/contract/check_test_registry.py`
  - `uv run --locked python tests/contract/check_shared_cache_policy.py`
  - `uv run --locked python tests/contract/check_manifest_completeness.py`
  - `uv run --locked python tests/run.py --profile core`
  - `uv run --locked python tests/run.py --profile nightly`
- Acceptance: all pass

## Testing plan (TDD)
- Start by adding self-test fixtures that encode four reviewed bypasses:
  - `os.popen("lake ...")`
  - `from subprocess import *; run([...])`
  - local fake `ensure_workspace_lake_packages` spoof
  - fake delegation marker in comment/string
- Execute self-test command to confirm failures in old behavior.
- Implement detection/provenance fixes until all self-tests pass.

## Decision log
- Prefer AST-aware detection for provenance/call checks to reduce comment/string spoof risks.
- Keep fallback regex checks for deterministic compatibility where AST extraction cannot fully resolve dynamic expressions.
- Keep policy fail-closed for strict dirs (`tests/e2e/**`, `tests/stress/**`) once an execution API is observed.

## Rollback plan
- Revert `tests/contract/check_test_registry.py`.
- Run:
  - `uv run --locked python tests/contract/check_test_registry.py`
- Confirm behavior returns to previous gate state.

## Outcomes & retrospective (fill when done)
- Implemented hardening in `tests/contract/check_test_registry.py`:
  - Added deterministic `--self-test` suite (now 36 cases) covering known bypass families plus positive controls.
  - Replaced delegation detection with AST call-level detection and launcher-position checks (comment/string token spoof blocked).
  - Enforced ensure provenance with import-aware checker and rebinding/monkeypatch shadow detection (`assign`, param, import, globals/locals/setitem, setattr paths).
  - Expanded exec API detection to include `os.popen`, star imports, callable aliases, `getattr(...)` exec forms, and dynamic callable execution expressions.
  - Improved command-atom extraction with AST expression evaluation for string concatenation/join/format/replace, bytes tokens, and path constructors.
  - Added fail-closed Lean/Lake call-atom check for exec/dynamic-call contexts in non-strict dirs.
  - Added `tests/bench` to must-register roots so bench tests are now under hard registration enforcement.
  - Extended delegation detection to parse shell-string command vectors (`subprocess(..., shell=True)` and `os.system(...)`) and recognize trusted launcher forms.
- Validation results:
  - `uv run --locked python tests/contract/check_test_registry.py --self-test` -> PASS
  - `uv run --locked python tests/contract/check_test_registry.py` -> PASS
  - Injected temporary `tests/bench/_tmp_unregistered_bench_check.py` -> deterministic FAIL (then cleaned)
  - Function probes: shell-string/os.system delegation now both `requires=True` and `has_shared=True`
  - `uv run --locked python tests/contract/check_shared_cache_policy.py` -> PASS
  - `uv run --locked python tests/contract/check_manifest_completeness.py` -> PASS
  - `uv run --locked python -m py_compile tests/contract/check_test_registry.py` -> PASS
  - `uv run --locked python tests/run.py --profile core` -> FAIL (baseline unrelated gate: `TEST_ENV_INVENTORY.md` out of date)
  - `uv run --locked python tests/run.py --profile nightly` -> FAIL (same baseline unrelated gate)
