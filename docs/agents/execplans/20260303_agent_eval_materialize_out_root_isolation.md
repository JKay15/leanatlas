---
title: Isolate agent-eval materialize smoke out_root to avoid concurrent cleanup races
owner: leanatlas-maintainer
status: done
created: 2026-03-03
---

## Purpose / Big Picture
`nightly-mcp-healthcheck` currently fails intermittently during `lake test` because `tests/agent_eval/check_runner_materialize_mode.py` reuses and force-deletes a shared output directory. When two automation runs execute tests close in time, one process may mutate the directory while another process is removing it, leading to `OSError: [Errno 66] Directory not empty`. This plan makes the materialize smoke test use a per-run isolated temporary output root so concurrent runs no longer contend on the same path. The change is scoped to test behavior and deterministic contracts; no workflow schema change is needed.

## Glossary
- materialize smoke test: `tests/agent_eval/check_runner_materialize_mode.py`, a core-tier test that ensures one pack workspace can be materialized.
- out_root: output root directory passed to `tools/agent_eval/run_pack.py --out-root`.
- concurrent automation run: multiple Codex App automation threads running `lake test` in the same source workspace around the same time.

## Scope
In scope:
- `tests/agent_eval/check_runner_materialize_mode.py`
- New guard test under `tests/agent_eval/`
- Test registry/documentation updates (`tests/manifest.json`, generated test matrix, tests README)
- ExecPlan index/update docs for traceability

Out of scope:
- Codex App scheduler internals
- Automation cadence/prompt changes
- Phase6 pack/scenario semantics

## Interfaces and Files
- `tests/agent_eval/check_runner_materialize_mode.py`
  - Replace shared fixed out_root cleanup pattern with isolated temporary out_root per run.
- `tests/agent_eval/check_runner_materialize_out_root_isolation.py` (new)
  - Deterministic contract test that enforces isolation pattern in the materialize smoke test.
- `tests/manifest.json`
  - Register the new contract test.
- `docs/testing/TEST_MATRIX.md`
  - Regenerate after manifest update.
- `tests/README.md`
  - Add one line describing this concurrency-safety contract.
- `docs/agents/execplans/README.md`
  - Add this plan to current plans index.

## Milestones
1) Red test (TDD)
- Deliverables:
  - Add `tests/agent_eval/check_runner_materialize_out_root_isolation.py`.
  - Register it in `tests/manifest.json`.
- Commands:
  - `./.venv/bin/python tests/agent_eval/check_runner_materialize_out_root_isolation.py`
- Acceptance:
  - Fails against current implementation because shared cleanup (`shutil.rmtree`) is still present and no temporary isolated out_root is used.

2) Implement isolation in materialize smoke test
- Deliverables:
  - Update `tests/agent_eval/check_runner_materialize_mode.py` to allocate a per-run temporary out_root (no shared pre-clean).
- Commands:
  - `./.venv/bin/python tests/agent_eval/check_runner_materialize_out_root_isolation.py`
  - `./.venv/bin/python tests/agent_eval/check_runner_materialize_mode.py`
- Acceptance:
  - Isolation contract passes.
  - Materialize smoke test remains green.

3) Registry/docs sync + mandatory verification
- Deliverables:
  - Update `tests/README.md`, regenerate `docs/testing/TEST_MATRIX.md`, update execplan index.
- Commands:
  - `./.venv/bin/python tools/tests/generate_test_matrix.py --write`
  - `./.venv/bin/python tools/docs/generate_file_index.py --write`
  - `./.venv/bin/python tests/run.py --profile core`
  - `./.venv/bin/python tests/run.py --profile nightly`
  - `lake build`
- Acceptance:
  - Core and nightly profiles pass.
  - `lake build` succeeds.
  - File index/test matrix contracts remain up to date.

## Testing plan (TDD)
- New test:
  - `tests/agent_eval/check_runner_materialize_out_root_isolation.py`
  - Enforces that materialize smoke test uses temporary isolated out_root API and avoids shared `shutil.rmtree` cleanup call.
- Regression scenario covered:
  - Prevent reintroduction of shared out_root deletion pattern that caused `Errno 66` under concurrent runs.
- Contamination control:
  - Materialize smoke test writes to temporary paths outside tracked repo files; no committed artifacts/logs.

## Decision log
- Decision: enforce isolation at test out_root allocation point.
- Why:
  - Race root cause is path contention, not business logic in Phase6 runner.
  - Smallest safe fix is to avoid shared directory reuse entirely.
- Rejected alternative: wrap `shutil.rmtree` with retries only.
  - Reason: hides contention symptoms but still keeps shared mutable path.

## Rollback plan
- Revert:
  - `tests/agent_eval/check_runner_materialize_mode.py`
  - `tests/agent_eval/check_runner_materialize_out_root_isolation.py`
  - `tests/manifest.json`
  - `tests/README.md`
  - `docs/testing/TEST_MATRIX.md`
  - `docs/agents/execplans/README.md`
- Verify rollback:
  - `./.venv/bin/python tests/run.py --profile core`

## Outcomes & retrospective
- Implemented per-run temporary out_root allocation in:
  - `tests/agent_eval/check_runner_materialize_mode.py`
  - Removed shared-path pre-clean (`shutil.rmtree`) to eliminate concurrent deletion contention.
- Added deterministic guard test:
  - `tests/agent_eval/check_runner_materialize_out_root_isolation.py`
  - Verifies temp out_root API is used and shared cleanup pattern is not reintroduced.
- Registry/docs synced:
  - `tests/manifest.json`
  - `tests/README.md`
  - `docs/testing/TEST_MATRIX.md` (regenerated)
  - `docs/navigation/FILE_INDEX.md` (regenerated)
  - `docs/agents/execplans/README.md`
- Verification results:
  - `./.venv/bin/python tests/agent_eval/check_runner_materialize_out_root_isolation.py` (red before fix, green after fix)
  - `./.venv/bin/python tests/agent_eval/check_runner_materialize_mode.py` (green)
  - `./.venv/bin/python tests/run.py --profile core` (green)
  - `./.venv/bin/python tests/run.py --profile nightly` (green; real-agent nightly checks skipped without `LEANATLAS_REAL_AGENT_CMD`)
  - `lake build` (green)
