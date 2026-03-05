---
title: Build LOOP Wave-A foundation (contracts + schemas + deterministic gates) before runtime implementation
owner: Codex (local workspace)
status: done
created: 2026-03-05
---

## Purpose / Big Picture
We have finalized LOOP architecture decisions in experimental notes, including filesystem layout, non-blocking audit semantics, dynamic exception recovery bounds, and migration strategy. The correct next step is to freeze the canonical Wave-A foundation in repository contracts/schemas/tests before touching runtime code. This reduces churn and prevents semantic drift when later implementing LOOP runtime and MCP surfaces. After Wave-A, the project should have machine-checkable contracts for LOOP definitions/runs/graphs/resource arbitration/audit and deterministic policy checks that block invalid states. This plan is intentionally implementation-ready but not yet executed.

## Glossary
- Wave A: first migration wave that only establishes contracts, schemas, and deterministic gate checks.
- Execution track (node runtime): `PENDING -> RUNNING -> AI_REVIEW -> (RUNNING | PASSED | FAILED | TRIAGED)`.
- Audit track: asynchronous audit lifecycle (`AUDIT_PENDING` ...), non-blocking for execution.
- `AUDIT_FLAGGED`: post-hoc audit issue with mandatory remediation evidence, not an in-path blocker.
- Dynamic recovery LOOP: temporary system-mode loop graph used only for unresolved exceptions.
- `run_key`: deterministic hash key identifying a unique LOOP run instance.

## Scope
In scope:
- Add LOOP contracts in `docs/contracts/**`.
- Add LOOP schemas in `docs/schemas/**`.
- Add deterministic contract/schema/state-policy checks in `tests/contract/**` and schema fixtures.
- Add Python-SDK-facing contract hooks (function surface + error model + idempotency semantics) at spec/schema level.
- Register tests in `tests/manifest.json` and update test docs only as needed.

Out of scope:
- Runtime/orchestrator implementation under `tools/**` and `LeanAtlas/**`.
- MCP server code implementation.
- Promotion/cutover of existing workflows.
- Editing historical experiment artifacts in `.cache/**` (read-only evidence source).

Allowed directories:
- `docs/contracts/**`
- `docs/schemas/**`
- `tests/**`
- `docs/testing/**` (only if registry/matrix docs need updates)
- `docs/agents/execplans/**` (this plan and follow-up logs)

Forbidden directories for Wave-A:
- `tools/**`
- `LeanAtlas/**`
- `Problems/**`
- `.cache/**` (except read-only)

## Interfaces and Files
Planned new contracts:
- `docs/contracts/LOOP_RUNTIME_CONTRACT.md`
- `docs/contracts/LOOP_GRAPH_CONTRACT.md`
- `docs/contracts/LOOP_RESOURCE_ARBITER_CONTRACT.md`
- `docs/contracts/LOOP_AUDIT_CONTRACT.md`
- `docs/contracts/LOOP_MCP_CONTRACT.md`
- `docs/contracts/LOOP_PYTHON_SDK_CONTRACT.md`

Planned new schemas:
- `docs/schemas/LoopDefinition.schema.json`
- `docs/schemas/LoopRun.schema.json`
- `docs/schemas/LoopGraphSpec.schema.json`
- `docs/schemas/ResourceLease.schema.json`
- `docs/schemas/InstructionResolutionReport.schema.json`
- `docs/schemas/AuditFlaggedEvent.schema.json`
- `docs/schemas/LoopSDKCallContract.schema.json`

Planned tests and registrations:
- `tests/contract/check_loop_contract_docs.py`
- `tests/contract/check_loop_schema_validity.py`
- `tests/contract/check_loop_state_machine_policy.py`
- `tests/contract/check_loop_python_sdk_contract_surface.py`
- `tests/contract/check_loop_state_machine_sequences.py`
- `tests/contract/check_loop_policy_stress.py`
- `tests/schema/fixtures/loop/*` (positive/negative fixtures)
- `tests/manifest.json`
- `docs/testing/TEST_MATRIX.md` (if required by existing checks)

Python SDK readiness guardrail (Wave-A level):
- Wave-A does not implement SDK code, but must fully specify SDK-facing semantics so Wave-B can implement without contract churn.
- Required in contract/schema:
  - canonical Python API surface (e.g., `loop()`, `serial()`, `parallel()`, `run()`, `resume()`)
  - idempotency and retry semantics
  - error code taxonomy and deterministic failure classes
  - evidence/trace return structure

Key policy inputs (already decided, experimental source of truth):
- `.cache/leanatlas/tmp/loop_architecture_proto_v0_1/LOOP_DECISION_TABLE.v0_3.*`
- `.cache/leanatlas/tmp/loop_architecture_proto_v0_1/AUDIT_FLAGGED_POLICY.v0_1.*`
- `.cache/leanatlas/tmp/loop_architecture_proto_v0_1/LOOP_BOOTSTRAP_DECISIONS.v0_1.*`
- `.cache/leanatlas/tmp/loop_architecture_proto_v0_1/LOOP_REFACTOR_FILE_MIGRATION_POLICY.v0_1.*`

Execution-track clarification (important):
- This is **not** the Wave-A milestone sequence.
- Wave-A sequence is the 5 milestones below (contracts/schemas/tests work plan).
- Execution track is the per-node runtime state model that Wave-A contracts/schemas must define.
- Loop-back is required: `AI_REVIEW -> RUNNING` when issues are repairable and retry budget remains.
- Terminal behavior:
  - `PASSED`: review accepted.
  - `TRIAGED`: retry budget exhausted or unresolved blocker (including unresolved external dependency).
  - `FAILED`: non-retryable execution fault (e.g., hard contract violation/infrastructure fatal).

## Milestones
### 1) Contract freeze (docs first)
Deliverables:
- Draft all five LOOP contracts with explicit state enums, required fields, and invariants.
- Cross-link contracts to existing workflow/reporting contracts where needed.

Commands:
- `uv run --locked python tests/contract/check_doc_pack_completeness.py`
- `uv run --locked python tests/contract/check_setup_docs.py`

Acceptance:
- Contract files exist and are discoverable by existing doc-pack checks.
- No ambiguous state definitions between execution track and audit track.

### 2) Schema authoring via TDD
Deliverables:
- Add six LOOP schemas and initial fixtures.
- Add SDK-call contract schema and fixtures.
- Write schema validation tests before finalizing schema bodies.

Commands:
- `uv run --locked python tests/contract/check_loop_schema_validity.py`
- `uv run --locked python tests/schema/validate_schemas.py`

Acceptance:
- Positive fixtures pass and negative fixtures fail deterministically.
- `AUDIT_FLAGGED` schema requires severity/category/evidence fields.
- SDK-call schema enforces idempotency key, actor identity, and deterministic error code envelope.

### 3) Deterministic policy gate checks
Deliverables:
- Add state-machine policy checks for:
  - execution-track allowed transitions
  - execution-track retry loop (`AI_REVIEW -> RUNNING`) with bounded auto-repair budget
  - audit-track lifecycle transitions
  - non-blocking `AUDIT_FLAGGED` + promotion-block condition for S1/unresolved S2
- Validate dynamic recovery default bounds and tuning band constraints.
- Add sequence and stress checks (contract-level, deterministic):
  - scenario sequence tests for normal and exceptional paths
  - high-volume transition stress tests for policy validators

Commands:
- `uv run --locked python tests/contract/check_loop_state_machine_policy.py`
- `uv run --locked python tests/contract/check_loop_state_machine_sequences.py`
- `uv run --locked python tests/contract/check_loop_policy_stress.py`
- `uv run --locked python tests/run.py --profile core`

Acceptance:
- Invalid transition/path is rejected with stable error code(s).
- Policy checks are deterministic and independent of agent availability.
- Sequence tests cover at least:
  - happy path with one repair loop
  - repeated repair then TRIAGED
  - S1/S2/S3 audit follow-up routing
  - dynamic-exception entry/exit back to static flow
- Stress tests verify deterministic results under repeated randomized transition sets (seed pinned).

### 4) Test registry and docs sync
Deliverables:
- Register new tests in `tests/manifest.json`.
- Update `docs/testing/TEST_MATRIX.md` only if required by existing registry checks.

Commands:
- `uv run --locked python tests/contract/check_test_registry.py`
- `uv run --locked python tests/contract/check_test_matrix_up_to_date.py`

Acceptance:
- Registry checks pass; no orphan tests/docs mismatch.

### 5) Wave-A closure report (no runtime code yet)
Deliverables:
- Add short closure note in this ExecPlan:
  - what landed
  - command outputs summary
  - known risks deferred to Wave-B

Commands:
- `uv run --locked python tests/run.py --profile core`
- (optional, if touched nightly-scope files) `uv run --locked python tests/run.py --profile nightly`

Acceptance:
- Core profile passes after Wave-A changes.
- Runtime/MCP implementation remains untouched, preserving clean phase separation.

## Testing plan (TDD)
New tests (planned first):
- `tests/contract/check_loop_contract_docs.py`
- `tests/contract/check_loop_schema_validity.py`
- `tests/contract/check_loop_state_machine_policy.py`
- `tests/contract/check_loop_python_sdk_contract_surface.py`
- `tests/contract/check_loop_state_machine_sequences.py`
- `tests/contract/check_loop_policy_stress.py`

Fixture coverage:
- Loop definition minimal/extended valid cases.
- Loop run with `run_key` and deterministic evidence set.
- Audit flagged events: S1/S2/S3 valid cases and missing-field invalid cases.
- State transition negatives (forbidden edges).

Regression coverage:
- Prevent reintroducing blocking `HUMAN_REVIEW` in execution path.
- Prevent `AUDIT_FLAGGED` without remediation linkage.
- Prevent out-of-band dynamic recovery config without escalation marker.
- Ensure repairable review failures re-enter RUNNING instead of premature TRIAGED/FAILED.
- Prevent SDK contract drift from MCP/contract semantics (one source of truth on ids/errors/evidence envelope).

Contamination control:
- No writes to real Toolbox/Incubator or production runtime folders.
- Test-generated files confined to temporary paths under `.cache/leanatlas/**` or test tempdirs.

## Decision log
- Execute Wave-A before runtime to minimize rework and stabilize interfaces.
- Keep `AUDIT_FLAGGED` non-blocking but enforce quality gate tags for high severity.
- Keep dynamic recovery bounded by defaults plus explicit tuning band.
- Keep MCP unavailability degradation as a hard contract requirement.

## Rollback plan
- Revert only Wave-A contracts/schemas/tests/docs touched by this plan.
- Verify rollback by rerunning:
  - `uv run --locked python tests/run.py --profile core`
- Confirm no LOOP Wave-A checks remain registered in `tests/manifest.json`.

## Outcomes & retrospective (fill when done)
- Completed:
  - Added Wave-A LOOP contracts:
    - `docs/contracts/LOOP_RUNTIME_CONTRACT.md`
    - `docs/contracts/LOOP_GRAPH_CONTRACT.md`
    - `docs/contracts/LOOP_RESOURCE_ARBITER_CONTRACT.md`
    - `docs/contracts/LOOP_AUDIT_CONTRACT.md`
    - `docs/contracts/LOOP_MCP_CONTRACT.md`
    - `docs/contracts/LOOP_PYTHON_SDK_CONTRACT.md`
  - Added Wave-A LOOP schemas:
    - `docs/schemas/LoopDefinition.schema.json`
    - `docs/schemas/LoopRun.schema.json`
    - `docs/schemas/LoopGraphSpec.schema.json`
    - `docs/schemas/ResourceLease.schema.json`
    - `docs/schemas/InstructionResolutionReport.schema.json`
    - `docs/schemas/AuditFlaggedEvent.schema.json`
    - `docs/schemas/LoopSDKCallContract.schema.json`
  - Added deterministic contract/policy checks:
    - `tests/contract/check_loop_contract_docs.py`
    - `tests/contract/check_loop_schema_validity.py`
    - `tests/contract/check_loop_state_machine_policy.py`
    - `tests/contract/check_loop_state_machine_sequences.py`
    - `tests/contract/check_loop_python_sdk_contract_surface.py`
    - `tests/contract/check_loop_policy_stress.py`
  - Added LOOP schema fixtures:
    - `tests/contract/fixtures/loop/positive/*.json`
    - `tests/contract/fixtures/loop/negative/*.json`
  - Registered tests in `tests/manifest.json`.
  - Regenerated deterministic docs:
    - `docs/testing/TEST_MATRIX.md`
    - `docs/setup/TEST_ENV_INVENTORY.md`
- Verification summary:
  - Passed:
    - `uv run --locked python tests/contract/check_loop_contract_docs.py`
    - `uv run --locked python tests/contract/check_loop_schema_validity.py`
    - `uv run --locked python tests/contract/check_loop_state_machine_policy.py`
    - `uv run --locked python tests/contract/check_loop_state_machine_sequences.py`
    - `uv run --locked python tests/contract/check_loop_python_sdk_contract_surface.py`
    - `uv run --locked python tests/contract/check_loop_policy_stress.py`
    - `uv run --locked python tests/contract/check_test_registry.py`
    - `uv run --locked python tests/contract/check_test_matrix_up_to_date.py`
    - `uv run --locked python tests/contract/check_test_env_inventory_up_to_date.py`
    - `uv run --locked python tests/determinism/check_canonical_json.py`
    - `uv run --locked python tests/run.py --profile core`
    - `uv run --locked python tests/run.py --profile nightly`
- Deferred to Wave-B:
  - Runtime state persistence, resume engine, graph scheduler, MCP execution adapters
- Notes:
  - Two early validation failures were fixed during implementation:
    - canonical JSON formatting for new schemas
    - stale `docs/setup/TEST_ENV_INVENTORY.md` after adding tests
