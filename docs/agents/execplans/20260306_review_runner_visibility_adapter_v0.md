---
title: Reviewer visibility pack and provider-adapter hardening for LOOP closeout
owner: codex
status: done
created: 2026-03-06
---

## Purpose / Big Picture
Maintainer AI review closeout currently knows the review scope, but it does not freeze the wider context that the reviewer must see. That leaves two gaps. First, a provider review can run without the active instruction chain, relevant contracts, or verify evidence being made explicit. Second, provider process success is still too close to provider semantic success; an empty or non-terminal provider output can look superficially healthy unless the runner enforces a canonical terminal payload. This plan hardens the maintainer review path so reviewer input is materialized as a visibility/context pack and provider closeout is judged by canonical semantic completion rather than process exit alone.

## Glossary
- Visibility/context pack: append-only artifact that freezes review scope, instruction scope, required context refs, and provider evidence rules for one review run.
- Required context refs: immutable evidence refs that the reviewer must be able to inspect, such as the active ExecPlan, relevant contracts, targeted tests, and latest verify evidence.
- Provider adapter: deterministic logic that knows how one provider invocation is launched and how semantic completion is recognized.
- Semantic completion: a provider run that not only exits, but also emits an acceptable canonical reviewer message or equivalent terminal event.

## Scope
In scope:
- `tools/loop/review_runner.py` provider-adapter and context-pack hardening.
- LOOP contracts/tests/docs covering reviewer visibility requirements and semantic provider closeout.
- Maintainer LOOP artifacts for this task's graph materialization and closeout.

Out of scope:
- Generalizing beyond the current local `codex exec review` provider family.
- Changing `tools/workflow/run_cmd.py` transport semantics.
- Changing core LOOP graph schema shape.

## Interfaces and Files
- `tools/loop/review_runner.py`
  - Add a visibility/context pack artifact and require it before provider launch.
  - Separate provider transport success from semantic closeout success.
  - Introduce deterministic provider-adapter behavior for the local `codex exec review` surface.
- `tools/loop/__init__.py`
  - Export any new review-runner helper surfaces.
- `tests/contract/check_loop_review_runner.py`
  - Add red tests for missing instruction scope, missing required context refs, semantic idle/invalid provider outcomes, and visibility-pack artifacts.
- `tests/contract/check_loop_contract_docs.py`
- `docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md`
- `docs/contracts/LOOP_PYTHON_SDK_CONTRACT.md`
- `tests/manifest.json`
- `docs/testing/TEST_MATRIX.md`
- `docs/setup/TEST_ENV_INVENTORY.md`

## Milestones
1) Red tests for visibility/context pack and semantic closeout
- Deliverables:
  - updated `tests/contract/check_loop_review_runner.py`
  - updated `tests/contract/check_loop_contract_docs.py`
- Commands:
  - `uv run --locked python tests/contract/check_loop_review_runner.py`
  - `uv run --locked python tests/contract/check_loop_contract_docs.py`
- Acceptance:
  - reviewer-runner test fails before implementation because the new visibility/context and semantic-closeout requirements are not yet met.

2) Implement provider-adapter + visibility hardening
- Deliverables:
  - `tools/loop/review_runner.py`
  - export updates in `tools/loop/__init__.py`
- Commands:
  - `uv run --locked python tests/contract/check_loop_review_runner.py`
- Acceptance:
  - runner emits append-only context-pack evidence and passes the new targeted tests.

3) Sync contracts and maintainer-facing documentation
- Deliverables:
  - updated LOOP contracts/docs/registry/inventory files
- Commands:
  - `uv run --locked python tests/contract/check_loop_contract_docs.py`
  - `uv run --locked python tests/contract/check_test_registry.py`
  - `uv run --locked python tests/contract/check_test_matrix_up_to_date.py`
- Acceptance:
  - docs and registry checks pass with the new requirements.

4) Full verification and maintainer LOOP closeout
- Deliverables:
  - verification results recorded in this plan
  - maintainer graph closeout artifact for this task
- Commands:
  - `uv run --locked python tests/run.py --profile core`
  - `uv run --locked python tests/run.py --profile nightly`
  - `lake build`
- Acceptance:
  - verification commands pass
  - final closeout references a runner-produced AI review artifact or explicit tooling-triage evidence.

## Testing plan (TDD)
- Extend the existing contract test to cover:
  - missing `instruction_scope_refs` rejection
  - missing `required_context_refs` rejection
  - persisted visibility/context pack artifact
  - provider success with empty canonical response => tooling triage
  - provider output that never emits terminal semantic evidence => tooling triage
- Keep tests repo-local by using temporary workspaces and helper scripts only.

## Decision log
- 2026-03-06: keep provider scope narrow and harden only the local `codex exec review` adapter first; avoid speculative multi-provider abstraction.
- 2026-03-06: treat reviewer visibility as an explicit immutable pack, not an implicit side effect of repo-root cwd.

## Rollback plan
- Revert changes to:
  - `tools/loop/review_runner.py`
  - `tools/loop/__init__.py`
  - updated LOOP contracts/tests/registry docs
- Re-run:
  - `uv run --locked python tests/contract/check_loop_review_runner.py`
  - `uv run --locked python tests/contract/check_loop_contract_docs.py`

## Outcomes & retrospective (fill when done)
- Extended `tools/loop/review_runner.py` so maintainer review closure now freezes:
  - `scope_ref`
  - `context_pack_ref`
  - normalized `instruction_scope_refs`
  - normalized `required_context_refs`
  - provider adapter metadata and semantic response source
- Strengthened instruction-scope validation from "some `AGENTS.md` present" to "active `AGENTS.md` chain induced by scoped files and required-context refs is present".
- Strengthened terminal-event extraction so canonical response synthesis can descend into nested `item` payloads as well as direct terminal message shapes.
- Expanded `tests/contract/check_loop_review_runner.py` to cover:
  - missing active-chain entries
  - nested terminal-event extraction
  - existing stale/timeout/missing-response success and triage paths
- Synced LOOP contracts and setup inventory:
  - `docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md`
  - `docs/contracts/LOOP_PYTHON_SDK_CONTRACT.md`
  - `docs/setup/TEST_ENV_INVENTORY.md`
  - `tests/contract/check_loop_contract_docs.py`
- Verification after repair:
  - `uv run --locked python tests/contract/check_loop_review_runner.py` PASS
  - `uv run --locked python tests/contract/check_loop_contract_docs.py` PASS
  - `uv run --locked python tests/contract/check_loop_wave_execution_policy.py` PASS
  - `uv run --locked python tests/run.py --profile core` PASS
  - `uv run --locked python tests/run.py --profile nightly` PASS (`real-agent` entries SKIP as designed because provider env vars are unset)
  - `lake build` PASS
  - `git diff --check` PASS
- AI review retrospective:
  - first provider attempt surfaced two real repair items through live JSON events, then became stale after those repairs
  - second provider attempt still failed to emit a canonical terminal message and was closed as tooling triage; evidence:
    - `artifacts/reviews/20260306_review_runner_visibility_adapter_review_round2_triage.md`
- Recommended next step:
  - add semantic-idle detection so `run_review_closure(...)` can terminate provider warning churn without manual intervention.
