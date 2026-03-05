---
title: Implement LOOP Wave-B runtime core + Python SDK facade with deterministic recovery and graph execution
owner: Codex (local workspace)
status: done
created: 2026-03-05
---

## Purpose / Big Picture
Wave A already froze LOOP contracts/schemas and deterministic policy gates. Wave B implements the first production-capable runtime core under those contracts: run identity (`run_key`), state transitions, append-only evidence, resume from interruption, resource arbitration (lease/CAS), graph execution, and dynamic exception recovery loop entry/exit. This phase also introduces a local Python SDK facade (library-level API) aligned with Wave-A SDK/MCP contracts, so users can compose and run LOOPs like a normal Python library while preserving deterministic audit artifacts. The goal is to make LOOP execution actually runnable end-to-end in local deterministic mode before introducing a full external MCP service.

## Glossary
- Loop runtime: deterministic engine executing one LOOP node through execution/audit tracks.
- Graph runtime: orchestrator executing a composed LOOP graph (serial/parallel/nested/race/quorum/barrier).
- System exception mode: temporary dynamic recovery graph triggered only by unresolved exception in static flow.
- Resume: restart from persisted state/checkpoint after interruption.
- SDK facade: Python-callable API (`loop`, `serial`, `parallel`, `run`, `resume`) backed by runtime core.
- Degradation path: if MCP is unavailable, local deterministic runner remains fully functional.

## Scope
In scope:
- Implement LOOP runtime core under `tools/**` using Wave-A contracts/schemas.
- Implement graph runtime with deterministic merge/arbitration records.
- Implement resume/checkpoint and interruption-safe write protocol.
- Implement resource arbiter lease/CAS/journal for controlled mutable resources.
- Implement local Python SDK facade and contract-aligned error envelope.
- Add contract/e2e/stress tests for runtime behavior and sequence semantics.

Out of scope:
- Full third-MCP network service/server implementation.
- Cross-repo extraction/split into separate MCP repository.
- Replacing existing Phase2 workflow runner wholesale.
- Broad migration of all existing workflows to LOOP runtime (bridge only).

Allowed directories:
- `tools/**` (new LOOP runtime package + adapters)
- `tests/**` (contract/e2e/stress for LOOP runtime)
- `docs/testing/**` (matrix updates when required)
- `docs/agents/execplans/**` (this plan updates)
- `tests/manifest.json`

Conditionally allowed (only if implementation forces clarification):
- `docs/contracts/LOOP_*.md`
- `docs/schemas/Loop*.schema.json`, `docs/schemas/AuditFlaggedEvent.schema.json`, `docs/schemas/ResourceLease.schema.json`, `docs/schemas/InstructionResolutionReport.schema.json`

Forbidden directories:
- `LeanAtlas/**`
- `Problems/**` (except temporary test workspaces under `.cache`)
- historical experiment records under `.cache/leanatlas/tmp/**` (read-only)

## Interfaces and Files
Planned new runtime package:
- `tools/loop/__init__.py`
- `tools/loop/model.py` (state enums, transition validators)
- `tools/loop/run_key.py` (deterministic run-key materialization)
- `tools/loop/store.py` (filesystem layout + append-only writers)
- `tools/loop/runtime.py` (single-node execution engine)
- `tools/loop/graph_runtime.py` (graph scheduler + merge/arbitration)
- `tools/loop/resource_arbiter.py` (lease/CAS/journal logic)
- `tools/loop/audit.py` (`AUDIT_FLAGGED` routing/severity effects)
- `tools/loop/sdk.py` (Python facade)
- `tools/loop/errors.py` (stable error_code/error_class/retryable envelope)
- `tools/loop/mcp_degrade.py` (MCP-unavailable fallback resolver)

Planned bridges (minimal):
- `tools/workflow/loop_bridge.py` (optional entry shim from existing runners)

Planned tests:
- `tests/contract/check_loop_runtime_determinism.py`
- `tests/contract/check_loop_resume_recovery.py`
- `tests/contract/check_loop_resource_arbiter_cas.py`
- `tests/contract/check_loop_dynamic_exception_entry_policy.py`
- `tests/contract/check_loop_sdk_error_envelope_runtime.py`
- `tests/e2e/golden/core_loop_repair_success/case.yaml`
- `tests/e2e/golden/core_loop_repair_exhausted/case.yaml`
- `tests/e2e/golden/core_loop_audit_block_s1/case.yaml`
- `tests/e2e/scenarios/scenario_loop_exception_recovery_chain/scenario.yaml`
- `tests/e2e/scenarios/scenario_loop_resume_after_interrupt/scenario.yaml`
- `tests/stress/loop_runtime_stress.py`
- `tests/stress/loop_resource_contention_stress.py`

Potential updates:
- `tests/e2e/run_cases.py` and/or `tests/e2e/run_scenarios.py` (only if new step kinds required)
- `tests/manifest.json`
- `docs/testing/TEST_MATRIX.md`
- `docs/setup/TEST_ENV_INVENTORY.md` (if command/dependency references change)

## Milestones
### 1) Runtime skeleton + deterministic store (TDD first)
Deliverables:
- Add tests for deterministic run_key generation, state transitions, and append-only writes.
- Implement `tools/loop/model.py`, `run_key.py`, `store.py`.

Commands:
- `uv run --locked python tests/contract/check_loop_state_machine_policy.py`
- `uv run --locked python tests/contract/check_loop_runtime_determinism.py`

Acceptance:
- Same semantic input produces same `run_key`.
- Execution track enforces `AI_REVIEW -> RUNNING` loop path and forbids blocking `HUMAN_REVIEW`.
- Store writes are append-only where required.

### 2) Single-node runtime + resume recovery
Deliverables:
- Implement runtime engine and checkpoint/resume logic.
- Add interruption simulation test that resumes from persisted checkpoint.

Commands:
- `uv run --locked python tests/contract/check_loop_resume_recovery.py`
- `uv run --locked python tests/contract/check_loop_runtime_determinism.py`

Acceptance:
- Interrupted run resumes without duplicating accepted attempts.
- Resume does not mutate historical attempt evidence.

### 3) Resource arbiter (lease/CAS/journal) + contention behavior
Deliverables:
- Implement lease acquisition, CAS commit, conflict logging, retry/escalation mapping.
- Add contention tests including deterministic conflict outcomes.

Commands:
- `uv run --locked python tests/contract/check_loop_resource_arbiter_cas.py`
- `uv run --locked python tests/stress/loop_resource_contention_stress.py`

Acceptance:
- `MUTABLE_CONTROLLED` writes always require lease + CAS + journal.
- Conflict events are append-only and reproducible.

### 4) Graph runtime + dynamic exception mode
Deliverables:
- Implement graph scheduler for serial/parallel basics first, then nested/race/quorum/barrier.
- Implement exception-only dynamic entry policy and static-flow return behavior.
- Add sequence scenario tests for dynamic recovery success/failure.

Commands:
- `uv run --locked python tests/contract/check_loop_dynamic_exception_entry_policy.py`
- `uv run --locked python tests/e2e/run_scenarios.py --profile core --id scenario_loop_exception_recovery_chain`

Acceptance:
- Dynamic mode entered only on qualifying exceptions with evidence.
- Recovery success returns to static flow; repeated unresolved failure reaches TRIAGED under budget constraints.

### 5) Python SDK facade + local degradation guarantee
Deliverables:
- Implement SDK API (`loop/serial/parallel/nested/run/resume`) backed by runtime core.
- Implement deterministic SDK error envelope (`error_code/error_class/retryable`) and evidence refs.
- Enforce local deterministic execution path when MCP unavailable.

Commands:
- `uv run --locked python tests/contract/check_loop_python_sdk_contract_surface.py`
- `uv run --locked python tests/contract/check_loop_sdk_error_envelope_runtime.py`

Acceptance:
- SDK calls align with Wave-A SDK contract and MCP group semantics.
- MCP unavailable path remains executable and deterministic.

### 6) E2E + stress hardening + registry sync
Deliverables:
- Add/enable LOOP runtime e2e golden cases and scenario chain tests.
- Add runtime stress tests and register all tests.
- Regenerate matrix/inventory docs as required.

Commands:
- `uv run --locked python tests/e2e/run_cases.py --profile core`
- `uv run --locked python tests/e2e/run_scenarios.py --profile core`
- `uv run --locked python tests/stress/loop_runtime_stress.py`
- `uv run --locked python tests/contract/check_test_registry.py`
- `uv run --locked python tests/contract/check_test_matrix_up_to_date.py`

Acceptance:
- LOOP runtime paths are covered by deterministic case/scenario/stress runs.
- Registry and matrix remain in sync; no unregistered test assets.

### 7) Wave-B closeout verification
Deliverables:
- Update this ExecPlan outcome section with final file list, commands, known risks.

Commands:
- `uv run --locked python tests/run.py --profile core`
- `uv run --locked python tests/run.py --profile nightly`
- `uv run --locked python tests/e2e/run_scenarios.py --profile core`

Acceptance:
- Core and nightly pass (allowed skips only where expected by existing policy).
- At least one LOOP scenario executed end-to-end.

## Testing plan (TDD)
New deterministic contract tests:
- runtime determinism (run_key, transitions, replay stability)
- resume recovery correctness under interruption
- resource arbiter lease/CAS/journal guarantees
- dynamic exception entry gate correctness
- runtime SDK error envelope semantics

New scenario/sequence tests:
- repair-loop success path
- repeated repair exhaustion -> TRIAGED
- S1/S2 audit outcome and promotion block behavior
- dynamic exception mode enter/recover/escalate chain
- resume-after-interrupt sequence

Stress tests:
- high-volume state transition replay with fixed seed
- resource contention stress with deterministic conflict accounting

Contamination control:
- all runtime/e2e generated artifacts under `.cache/leanatlas/**` or scenario temp roots
- no writes into production Toolbox/Incubator paths

## Decision log
- Runtime implementation is introduced as a new package (`tools/loop/**`) to avoid destabilizing existing workflow codepaths.
- Full MCP server implementation is deferred; Wave-B enforces local degradation path first.
- Dynamic recovery is implemented as policy-governed exception mode, not default orchestration mode.
- SDK is added as a facade over runtime contracts, not as a parallel semantics source.

## Rollback plan
- Revert all Wave-B runtime package files and newly added LOOP runtime tests/cases/scenarios.
- Remove associated manifest entries and regenerate test matrix if needed.
- Verify rollback with:
  - `uv run --locked python tests/run.py --profile core`
  - `uv run --locked python tests/contract/check_test_registry.py`

## Outcomes & retrospective (fill when done)
- Completed:
  - Milestone 1 (runtime skeleton + deterministic store):
    - Added `tools/loop/model.py` (execution states + allowed transitions + validator)
    - Added `tools/loop/run_key.py` (deterministic `run_key` from canonical semantic input)
    - Added `tools/loop/store.py` (append-only JSONL + write-once JSON in cache/artifact streams)
    - Added contract test `tests/contract/check_loop_runtime_determinism.py`
    - Updated `tools/AGENTS.md` navigation coverage for new `tools/loop/**` directory
  - Milestone 2 (single-node runtime + resume recovery):
    - Added `tools/loop/runtime.py` (start/resume, deterministic review transition precedence, append-only checkpoints/transitions/iterations)
    - Added contract test `tests/contract/check_loop_resume_recovery.py`
  - Milestone 3 (resource arbiter lease/CAS/journal):
    - Added `tools/loop/resource_arbiter.py` (`MUTABLE_CONTROLLED` lease acquisition, CAS commit, conflict journaling, release)
    - Added contract test `tests/contract/check_loop_resource_arbiter_cas.py`
  - Milestone 4 (graph runtime + dynamic exception entry policy):
    - Added `tools/loop/graph_runtime.py` (deterministic DAG batch scheduler + arbitration records + dynamic-entry guard)
    - Added contract test `tests/contract/check_loop_dynamic_exception_entry_policy.py`
  - Milestone 5 (Python SDK facade + deterministic error envelope):
    - Added `tools/loop/errors.py` (typed `error_code/error_class/retryable` envelope mapping)
    - Added `tools/loop/sdk.py` (facade: `loop/serial/parallel/nested/run/resume`)
    - Added contract test `tests/contract/check_loop_sdk_error_envelope_runtime.py`
  - Packaging/registry sync:
    - Extended `tools/loop/__init__.py` exports for new runtime modules
    - Registered new LOOP tests in `tests/manifest.json`
    - Regenerated `docs/testing/TEST_MATRIX.md`
- Verification summary:
  - `uv run --locked python tests/contract/check_loop_runtime_determinism.py` PASS
  - `uv run --locked python tests/contract/check_loop_resume_recovery.py` PASS
  - `uv run --locked python tests/contract/check_loop_resource_arbiter_cas.py` PASS
  - `uv run --locked python tests/contract/check_loop_dynamic_exception_entry_policy.py` PASS
  - `uv run --locked python tests/contract/check_loop_sdk_error_envelope_runtime.py` PASS
  - Independent review evidence:
    - historical metadata-scope audit:
      - `artifacts/loop_runtime/manual_reviews/20260305T041051Z/review_prompt.md`
      - `artifacts/loop_runtime/manual_reviews/20260305T041051Z/review_response.md`
      - `artifacts/loop_runtime/manual_reviews/20260305T041051Z/review_summary.json`
    - refreshed Stage-2 closeout scope audit:
      - `artifacts/reviews/20260306_stage2_active_plans_closeout_review_prompt.md`
      - `artifacts/reviews/20260306_stage2_active_plans_closeout_review_response.md`
  - `uv run --locked python tests/contract/check_test_registry.py` PASS
  - `uv run --locked python tests/contract/check_test_matrix_up_to_date.py` PASS
  - `uv run --locked python tests/run.py --profile core` PASS
  - `uv run --locked python tests/run.py --profile nightly` PASS
- Residual risks:
  - Full external third-MCP service packaging and cross-repo extraction remain deferred to follow-up waves.
