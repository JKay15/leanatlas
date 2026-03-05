---
title: Productize theorem-formalization experiments into first-class workflow gates (replace/upgrade, not stack)
owner: Codex (local workspace)
status: done
created: 2026-03-04
---

## Purpose / Big Picture
The current theorem/lemma formalization pipeline is powerful but lives in isolated `.cache` experiments. That is good for exploration, but it creates integration risk: duplicated logic, parallel state machines, and weak long-term maintainability. This plan productizes the proven parts into repository contracts/schemas/tools so the workflow can be executed, audited, and tested in one canonical path. The target is not a file copy from experiment to mainline; it is capability replacement with explicit deprecation and compatibility bridges. After this work, formalization governance (proof completion, anti-cheat, mapping alignment, external dependency hooks) should be first-class and provider-neutral in the LeanAtlas workflow. Deterministic Judge authority remains final; agent outputs stay advisory.

## Glossary
- Experimental stack: assets under `.cache/leanatlas/tmp/theorem_proof_proto_v0_2/**` and `.cache/leanatlas/tmp/arxiv_2112_13254v3_proto_v0_3/**`.
- Productized stack: committed contracts/schemas/tools/tests in main repository paths.
- Capability replacement: moving a feature into canonical modules and marking experimental implementation as non-authoritative.
- Compatibility bridge: deterministic converters/adapters allowing old experiment artifacts to feed new interfaces during migration.
- Formalization gate family: checks about proof completeness, anti-cheat, strong validation, and unresolved dependencies.
- Mapping gate family: checks about Lean declaration/object to atom/clause alignment completeness and correctness.

## Scope
In scope:
- Add first-class formalization contracts/schemas and deterministic tooling entrypoints.
- Integrate formalization + mapping dual-gate decisions into the existing workflow/Judge contract model.
- Introduce migration adapters from experiment artifacts to product schemas.
- Add contract/schema/e2e tests and update docs/testing registry.
- Define deprecation policy for experimental scripts without deleting audit evidence.

Out of scope:
- Rewriting historical experiment logs under `.cache/**`.
- Re-formalizing every paper immediately; this plan builds the platform path.
- Forcing external-paper theorem retrieval to be complete in v0.

Allowed directories to change:
- `docs/contracts/**`
- `docs/schemas/**`
- `tools/**`
- `tests/**`
- `docs/agents/**` (this ExecPlan and required usage docs)
- `docs/testing/**` (if matrix/docs regeneration is needed)

Forbidden directories:
- `.cache/**` experiment assets (read-only input/evidence source)
- `LeanAtlas/**` theorem libraries not required by formalization platform wiring
- unrelated `Problems/**` content

## Replacement And Optimization Policy
This migration follows replacement/coverage/optimization, not additive stacking:

| Capability | Experimental source | Product target | Migration action |
|---|---|---|---|
| Theorem/lemma ledger (claim/proof/link/external metadata) | `TheoremProofLedger.v0_3` | `docs/schemas/FormalizationLedger.schema.json` + contract | Replace schema authority; keep deterministic adapter for old ledgers |
| Missing-proof state machine (`NEW -> CODEX_ATTEMPTED -> GPT52PRO_ESCALATED -> TRIAGED`) | `prepare/apply_proof_completion_*_v04.py` | `tools/formalization/worklist.py` + workflow contract section | Replace ad-hoc runner with canonical tool API; preserve states |
| Anti-cheat + semantic placeholder detection | `anti_cheat_gate_v04.py` | `tools/formalization/anti_cheat.py` + formalization contract | Replace script path; keep issue codes stable |
| Strong validation (`--error=warning`, axioms allowlist) | `strong_validation_gate_v04.py` | `tools/formalization/strong_validation.py` | Replace script path and standardize report schema |
| Dual-gate governor (`formalization` + `mapping`) | `governor_decide_cycle_v01.py` | `tools/workflow/formalization_governor.py` + `WORKFLOW_CONTRACT` extension | Replace parallel loop with canonical Judge-compatible interface |
| Resume/checkpoint apply | `apply_proof_completion_decisions_v04.py` | `tools/formalization/apply_decisions.py` | Replace implementation; retain deterministic resume fingerprint rules |
| Gate pluginization | `gate_conditions/*.json` + dispatcher | product gate policy schema + loader under `tools/workflow` | Upgrade to standard plugin contract and strict validation |
| Lean reverse links / atom mappings | ledger fields + resync scripts | formalization mapping contract + deterministic validators | Upgrade granularity checks and failure codes |
| One-command orchestration | `run_formalization_cycle_v04.sh` | provider-neutral Python entrypoint in `tools/workflow` | Replace shell glue with auditable command spans |

Optimization requirements:
- Single source of truth for each gate decision.
- No duplicate state machines for the same claim status in separate files.
- Shared issue code taxonomy across anti-cheat/validation/governor.
- Reuse existing provider abstraction (`agent_provider.py`) for agent invocations.

## Interfaces and Files
Planned new files:
- `docs/contracts/FORMALIZATION_LEDGER_CONTRACT.md`
- `docs/contracts/FORMALIZATION_GOVERNANCE_CONTRACT.md`
- `docs/schemas/FormalizationLedger.schema.json`
- `docs/schemas/ProofCompletionWorklist.schema.json`
- `docs/schemas/ProofCompletionDecisionApplyReport.schema.json`
- `docs/schemas/FormalizationGateReport.schema.json`
- `docs/schemas/CodexFidelityReview.schema.json` (provider-neutral naming may be `AgentFidelityReview.schema.json`)
- `tools/formalization/__init__.py`
- `tools/formalization/build_worklist.py`
- `tools/formalization/apply_decisions.py`
- `tools/formalization/anti_cheat.py`
- `tools/formalization/strong_validation.py`
- `tools/formalization/adapters/upgrade_experimental_ledger.py`
- `tools/workflow/formalization_governor.py`

Planned updates:
- `docs/contracts/WORKFLOW_CONTRACT.md`
- `docs/contracts/REPORTING_CONTRACT.md`
- `docs/contracts/AI_NATIVE_ENGINEERING_CONTRACT.md` (if new anti-cheat expectations are normative)
- `docs/testing/TEST_MATRIX.md`
- `tests/manifest.json`
- `docs/agents/MAINTAINER_WORKFLOW.md` (formalization runbook section)
- `docs/agents/CODEX_APP_PROMPTS.md` (provider-neutral formalization prompts)

## Milestones
### 1) Contract/surface design freeze (replacement map first)
Deliverables:
- Add formalization contract skeletons and schema placeholders.
- Record field-level mapping from experiment schemas to product schemas.
- Publish deprecation table (what becomes non-authoritative and by when).

Commands:
- `uv run --locked python tests/contract/check_doc_pack_completeness.py`
- `uv run --locked python tests/schema/validate_schemas.py`

Acceptance:
- New contract+schema files are present and referenced by docs.
- Schema validation fails first (TDD red), then passes after fixture completion.

### 2) Deterministic tool core (no agent dependency)
Deliverables:
- Implement worklist/apply/anti-cheat/strong-validation deterministic modules under `tools/formalization`.
- Add compatibility adapter for experiment ledgers (`v0_2/v0_3/v0_4 artifacts -> product schema`).
- Keep issue-code continuity where possible.

Commands:
- `uv run --locked python tests/contract/check_tools_subprocess_wrapper.py`
- `uv run --locked python tests/schema/validate_schemas.py`
- `uv run --locked python tests/run.py --profile core`

Acceptance:
- Deterministic modules run without relying on agent output.
- Adapter can ingest existing experimental ledgers and emit product-valid artifacts.

### 3) Workflow/Judge integration (replace parallel orchestration)
Deliverables:
- Add formalization governor entrypoint under `tools/workflow`.
- Integrate dual-gate outcomes into deterministic Judge-compatible decisions.
- Preserve resume short-circuit semantics with explicit fingerprint evidence.

Commands:
- `uv run --locked python tests/contract/check_judge_determinism.py`
- `uv run --locked python tests/contract/check_retrievaltrace_invariants.py`
- `uv run --locked python tests/run.py --profile core`

Acceptance:
- Formalization/mapping branches are auditable in canonical workflow artifacts.
- No separate non-canonical state machine is required for production runs.

### 4) Test hardening (contract + e2e + contamination)
Deliverables:
- Add new contract tests for formalization schemas/contracts.
- Add schema positive/negative fixtures.
- Add at least one executable e2e scenario using temporary workspace overlay under `.cache/leanatlas/**`.

Commands:
- `uv run --locked python tests/run.py --profile core`
- `uv run --locked python tests/e2e/run_scenarios.py --profile core`

Acceptance:
- E2E proves end-to-end formalization gate loop with deterministic outputs.
- No test pollution into real Toolbox/Incubator paths.

### 5) Rollout and deprecation bridge
Deliverables:
- Publish migration guide from experimental commands to product commands.
- Add warnings in experiment entrypoints indicating non-authoritative status.
- Keep backward-compatible adapters for transition window.

Commands:
- `uv run --locked python tests/contract/check_setup_docs.py`
- `uv run --locked python tests/contract/check_test_registry.py`
- `uv run --locked python tests/contract/check_test_matrix_up_to_date.py`

Acceptance:
- Users can run the new path directly from docs.
- Legacy experiment path remains readable for audit but is no longer default.

## Testing plan (TDD)
New tests (planned):
- `tests/contract/check_formalization_contract_surface.py`
- `tests/contract/check_formalization_governor_policy_contract.py`
- `tests/contract/check_formalization_resume_fingerprint_policy.py`
- `tests/schema/fixtures/formalization_ledger/*`
- `tests/schema/fixtures/proof_completion_worklist/*`
- `tests/schema/fixtures/formalization_gate_report/*`
- `tests/e2e/scenarios/scenario_formalization_governor.yaml`
- `tests/e2e/check_formalization_governor_flow.py`

Regression scenarios:
- hidden placeholder patterns compile but must fail gate
- unresolved non-external dependency must block accept gate
- mapping-only edits must short-circuit formalization gate on resume
- TRIAGED transition must include complete evidence bundle

Contamination control:
- all generated data under `.cache/leanatlas/**` or scenario temp roots
- no test writes into `LeanAtlas/Toolbox/**` or committed Incubator content

## Decision log
- Prefer product schema names independent of a paper slug to avoid one-off lock-in.
- Keep dual-gate (`formalization` + `mapping`) because it enables efficient short-circuit and cleaner failure diagnosis.
- Keep deterministic Judge as authority; agent review remains advisory evidence.
- Use adapters rather than direct schema replacement to protect historical experiment replayability.
- Keep external dependency unresolved status as explicit blocking/triage signal, not silent pass.

## Rollback plan
- Revert newly added formalization contracts/schemas/tools/tests.
- Keep experimental `.cache` workflow untouched as fallback path.
- Verify rollback by running:
  - `uv run --locked python tests/run.py --profile core`
  - targeted formalization tests should disappear from manifest/matrix in the same rollback commit.

## Outcomes & retrospective (fill when done)
- Completed:
  - Milestone 1 (contract/surface design freeze):
    - Added canonical formalization contracts and schemas:
      - `docs/contracts/FORMALIZATION_LEDGER_CONTRACT.md`
      - `docs/contracts/FORMALIZATION_GOVERNANCE_CONTRACT.md`
      - `docs/schemas/FormalizationLedger.schema.json`
      - `docs/schemas/ProofCompletionWorklist.schema.json`
      - `docs/schemas/ProofCompletionDecisionApplyReport.schema.json`
      - `docs/schemas/FormalizationGateReport.schema.json`
      - `docs/schemas/AgentFidelityReview.schema.json`
  - Milestone 2 (deterministic tool core):
    - Added deterministic runtime modules:
      - `tools/formalization/adapters/upgrade_experimental_ledger.py`
      - `tools/formalization/build_worklist.py`
      - `tools/formalization/apply_decisions.py`
      - `tools/formalization/anti_cheat.py`
      - `tools/formalization/strong_validation.py`
    - Added runtime contract gate:
      - `tests/contract/check_formalization_toolchain_runtime.py`
  - Milestone 3 (workflow/Judge integration):
    - Added deterministic dual-gate governor:
      - `tools/workflow/formalization_governor.py`
      - `tests/contract/check_formalization_governor_policy_contract.py`
    - Aligned workflow/governance contracts:
      - `docs/contracts/WORKFLOW_CONTRACT.md`
      - `docs/contracts/FORMALIZATION_GOVERNANCE_CONTRACT.md`
      - `docs/contracts/REPORTING_CONTRACT.md`
  - Milestone 4 (test hardening):
    - formalization schemas/fixtures/contract tests integrated into registry + matrix.
    - core e2e scenario path verified under shared overlay workspace (`.cache/leanatlas/**`).
  - Milestone 5 (rollout/deprecation bridge):
    - deterministic adapter path established as authoritative bridge from experimental ledgers to product schema.
    - formalization contract docs explicitly mark experimental artifacts as evidence sources but non-authoritative.
- Verification:
  - `uv run --locked python tests/contract/check_formalization_schema_policy.py` PASS
  - `uv run --locked python tests/contract/check_formalization_toolchain_runtime.py` PASS
  - `uv run --locked python tests/contract/check_formalization_governor_policy_contract.py` PASS
  - `uv run --locked python tests/schema/validate_schemas.py` PASS
  - `uv run --locked python tests/contract/check_test_registry.py` PASS
  - `uv run --locked python tests/contract/check_test_matrix_up_to_date.py` PASS
  - `uv run --locked python tests/e2e/run_scenarios.py --profile core --lake-timeout-s 600 --step-timeout-s 600` PASS
  - `uv run --locked python tests/run.py --profile core` PASS
  - `uv run --locked python tests/run.py --profile nightly` PASS
- Independent review evidence:
  - `artifacts/reviews/20260305_formalization_m1_schema_contract_fix_codex_exec_review.md` (`Verdict: PASS`)
  - `artifacts/reviews/20260305_formalization_tests_integration_codex_exec_review.md` (`Verdict: PASS`)
