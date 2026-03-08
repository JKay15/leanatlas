---
title: Fresh xhigh revalidation matrix for tiered default reviewer policy
owner: Codex (local workspace)
status: active
created: 2026-03-08
parent_execplan: docs/agents/execplans/20260307_loop_core_parallel_nested_batch_v0.md
---

## Purpose / Big Picture
This wave is an audit-only maintainer pass. The goal is not to add functionality or repair defects, but to re-validate already-closed LOOP/reviewer-policy work on a fresh `gpt-5.4-xhigh` pass and decide whether the current default reviewer strategy is stable enough to freeze as `FAST + low` baseline, `medium` standard escalation, and `STRICT / xhigh` exception only. The audit must use the repository's current head and real maintainer LOOP/review artifacts rather than relying on prior thread context. Every target is reviewed against its final authoritative state only; superseded intermediate rounds must remain historical context, not active scope. If new findings appear, they are recorded but not repaired in this wave unless a blocker makes the remaining matrix misleading.

## Glossary
- `authoritative final state`: the latest settled target state defined by the target ExecPlan outcome section, latest verify note, latest authoritative review summary/prompt/response, and maintainer LOOP closeout alias if present.
- `fresh xhigh`: a new review run executed today with `agent_profile = gpt-5.4-xhigh`, using the current repository bytes and a newly materialized context pack.
- `revalidation matrix`: the grouped audit table covering A/B/C targets, their historical closeout tier, fresh `xhigh` result, and policy implication.
- `historical closeout tier`: the reviewer tier that actually produced the settled clean closeout for the target (`xhigh`, `medium`, or `FAST/low`).

## Scope
In scope:
- Read and confirm the active master plan at `docs/agents/execplans/20260307_loop_core_parallel_nested_batch_v0.md`.
- Create and complete this audit ExecPlan.
- Materialize a fresh maintainer LOOP session for this audit so the validation itself proves the project can still maintain/close through LOOP without prior thread memory.
- Re-read the final authoritative evidence for each target group:
  - A: `docs/agents/execplans/20260307_review_orchestration_automation_v0.md`
  - B: `docs/agents/execplans/20260308_review_supersession_reconciliation_runtime_v0.md`, `docs/agents/execplans/20260308_review_tiered_default_policy_v0.md`
  - C: `docs/agents/execplans/20260307_loop_mainline_productization_integration_v0.md`, `docs/agents/execplans/20260308_loop_user_preferences_and_onboarding_defaults_v0.md`, `docs/agents/execplans/20260308_formalization_enrichment_absorption_v0.md`, `docs/agents/execplans/20260308_review_default_profile_policy_v0.md`, `docs/agents/execplans/20260307_maintainer_closeout_ref_v0.md`, `docs/agents/execplans/20260307_loop_core_parallel_nested_batch_v0.md`
- Run fresh `xhigh` reviews for the current final state of each target and preserve complete review artifacts.
- Produce a final matrix and answer the three reviewer-policy questions.

Out of scope:
- modifying `tools/**`, `docs/contracts/**`, `docs/schemas/**`, `tests/**`, or `LeanAtlas/**`
- repairing newly found issues during this wave
- re-litigating superseded intermediate review rounds as if they were current defects

Allowed changes:
- `docs/agents/execplans/20260308_xhigh_revalidation_matrix_v0.md`
- `artifacts/reviews/**`
- `artifacts/verify/**`
- `artifacts/loop_runtime/**`

Forbidden changes:
- system code, contracts, schemas, and tests

## Interfaces and Files
- `docs/agents/PLANS.md`: ExecPlan requirements.
- `docs/agents/execplans/20260307_loop_core_parallel_nested_batch_v0.md`: active master plan to confirm before proceeding.
- `tools/loop/maintainer.py`: maintainer LOOP materialization / node journaling / closeout.
- `tools/loop/review_runner.py`: canonical review runner for prompt/response/summary/canonical/attempt evidence.
- `docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md`
- `docs/contracts/LOOP_MCP_CONTRACT.md`
- `docs/contracts/LOOP_PYTHON_SDK_CONTRACT.md`
- `docs/schemas/WaveExecutionLoopRun.schema.json`
- `docs/schemas/LoopSDKCallContract.schema.json`
- `artifacts/reviews/*`: historical and fresh reviewer evidence.
- `artifacts/verify/*`: verify notes used to identify settled final state and to record this matrix.
- `artifacts/loop_runtime/by_execplan/*/MaintainerCloseoutRef.json`: settled maintainer LOOP closeout aliases for target plans and this audit plan.

Target groups and required historical anchors:
- Group A control:
  - `docs/agents/execplans/20260307_review_orchestration_automation_v0.md`
  - `artifacts/reviews/20260307_review_orchestration_automation_review_round19_strict_summary.json`
  - `artifacts/reviews/20260307_review_orchestration_automation_review_round30_strict_summary.json`
  - `artifacts/reviews/20260307_review_orchestration_automation_review_round37_strict_summary.json`
  - `artifacts/reviews/20260307_review_orchestration_automation_review_round46_strict_summary.json`
- Group B medium closeout:
  - `docs/agents/execplans/20260308_review_supersession_reconciliation_runtime_v0.md`
  - `docs/agents/execplans/20260308_review_tiered_default_policy_v0.md`
  - `artifacts/reviews/20260308_review_supersession_reconciliation_runtime_review_round6_medium_summary.json`
  - `artifacts/reviews/20260308_review_tiered_default_policy_review_round8_medium_summary.json`
- Group C fast/low closeout:
  - `docs/agents/execplans/20260307_loop_mainline_productization_integration_v0.md`
  - `docs/agents/execplans/20260308_loop_user_preferences_and_onboarding_defaults_v0.md`
  - `docs/agents/execplans/20260308_formalization_enrichment_absorption_v0.md`
  - `docs/agents/execplans/20260308_review_default_profile_policy_v0.md`
  - `docs/agents/execplans/20260307_maintainer_closeout_ref_v0.md`
  - `docs/agents/execplans/20260307_loop_core_parallel_nested_batch_v0.md`
  - `artifacts/reviews/20260307_loop_mainline_productization_integration_review_round2_fast_summary.json`
  - `artifacts/reviews/20260308_user_prefs_formalization_frontier_review_round6_fast_summary.json`
  - `artifacts/reviews/20260308_review_default_profile_policy_review_round3_fast_summary.json`
  - `artifacts/reviews/20260307_maintainer_closeout_ref_review_round11_fast_part_01_docs_summary.json`
  - `artifacts/reviews/20260307_maintainer_closeout_ref_review_round11_fast_part_02_tests_summary.json`
  - `artifacts/reviews/20260307_maintainer_closeout_ref_review_round11_fast_part_03_tools_summary.json`
  - `artifacts/reviews/20260307_loop_core_parallel_nested_batch_review_round2_summary.json`

## Milestones
### 1) Freeze audit authority and materialize maintainer LOOP session
Deliverables:
- This ExecPlan becomes the audit authority for the fresh `xhigh` revalidation wave.
- A fresh maintainer LOOP session is materialized for this audit before any review execution.

Commands:
- `sed -n '1,220p' docs/agents/PLANS.md`
- `sed -n '1,260p' docs/agents/execplans/20260307_loop_core_parallel_nested_batch_v0.md`
- `uv run --locked python - <<'PY'`
  `from pathlib import Path`
  `from tools.loop.maintainer import MaintainerLoopSession`
  `session = MaintainerLoopSession.materialize(`
  `    repo_root=Path('.').resolve(),`
  `    change_id='xhigh_revalidation_matrix_v0',`
  `    execplan_ref='docs/agents/execplans/20260308_xhigh_revalidation_matrix_v0.md',`
  `    scope_paths=[`
  `        'docs/agents/execplans/20260307_review_orchestration_automation_v0.md',`
  `        'docs/agents/execplans/20260308_review_supersession_reconciliation_runtime_v0.md',`
  `        'docs/agents/execplans/20260308_review_tiered_default_policy_v0.md',`
  `        'docs/agents/execplans/20260307_loop_mainline_productization_integration_v0.md',`
  `        'docs/agents/execplans/20260308_loop_user_preferences_and_onboarding_defaults_v0.md',`
  `        'docs/agents/execplans/20260308_formalization_enrichment_absorption_v0.md',`
  `        'docs/agents/execplans/20260308_review_default_profile_policy_v0.md',`
  `        'docs/agents/execplans/20260307_maintainer_closeout_ref_v0.md',`
  `        'docs/agents/execplans/20260307_loop_core_parallel_nested_batch_v0.md',`
  `    ],`
  `    instruction_scope_refs=['AGENTS.md', 'AGENTS.override.md'],`
  `    required_context_refs=[`
  `        'docs/agents/PLANS.md',`
  `        'docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md',`
  `        'docs/contracts/LOOP_MCP_CONTRACT.md',`
  `        'docs/contracts/LOOP_PYTHON_SDK_CONTRACT.md',`
  `        'docs/schemas/WaveExecutionLoopRun.schema.json',`
  `        'docs/schemas/LoopSDKCallContract.schema.json',`
  `    ],`
  `)`
  `print(session.run_key)`
  `print(session.session_ref)`
  `print(session.progress_ref)`
  `PY`

Acceptance:
- A fresh maintainer session exists under `artifacts/loop_runtime/by_key/<run_key>/graph/`.
- The session freezes this ExecPlan, audit scope, and required LOOP contracts without relying on prior chat context.

### 2) Re-run deterministic sanity verification on current head
Deliverables:
- Fresh read-only verification evidence that current LOOP/reviewer-policy surfaces still satisfy the committed contracts before any new `xhigh` conclusion is drawn.

Commands:
- `uv run --locked python tests/contract/check_loop_contract_docs.py`
- `uv run --locked python tests/contract/check_loop_schema_validity.py`
- `uv run --locked python tests/contract/check_loop_wave_execution_policy.py`
- `uv run --locked python tests/contract/check_loop_python_sdk_contract_surface.py`
- `uv run --locked python tests/contract/check_skills_standard_headers.py`
- `uv run --locked python tests/run.py --profile core`
- `uv run --locked python tests/run.py --profile nightly`

Acceptance:
- Sanity checks pass on current head, or any failure is recorded as validation evidence and treated as a blocker/risk in the matrix.

### 3) Reconstruct each target's authoritative final review scope
Deliverables:
- For every target, record:
  - target ExecPlan
  - final verify note
  - final authoritative review summary / prompt / response
  - related maintainer LOOP closeout alias when present
  - final authoritative file scope to be re-reviewed today

Commands:
- `rg -n "verify note|latest|closeout|round[0-9]+|MaintainerCloseoutRef" docs/agents/execplans/<target>.md`
- `sed -n '1,220p' <verify-note>`
- `sed -n '1,260p' <final-prompt>`
- `sed -n '1,260p' <final-response>`
- `sed -n '1,220p' <final-summary>`
- `sed -n '1,220p' artifacts/loop_runtime/by_execplan/<stable_execplan_id>/MaintainerCloseoutRef.json`

Acceptance:
- Each target has one explicit authoritative final-state scope for fresh review.
- Superseded historical rounds remain cited only as background evidence, never as current scope.

### 4) Run fresh `gpt-5.4-xhigh` review for every authoritative final state
Deliverables:
- One new fresh `xhigh` review closure per target with complete artifacts:
  - prompt
  - response
  - summary
  - canonical payload
  - attempts evidence

Commands:
- `uv run --locked python - <<'PY'`
  `# For each target, call tools.loop.review_runner.run_review_closure(...) with:`
  `# - review_id rooted at 20260308_xhigh_revalidation_*`
  `# - prompt_path under artifacts/reviews/*_prompt.md`
  `# - response_path under artifacts/reviews/*_response.md`
  `# - scope_paths equal to the authoritative final-state file list`
  `# - command = ['codex', 'exec', 'review', '--profile', 'gpt-5.4-xhigh', '-o', <response_path>, <prompt_text>]`
  `# - agent_provider_id='codex_cli'`
  `# - agent_profile='gpt-5.4-xhigh'`
  `# - instruction_scope_refs including the active AGENTS chain`
  `# - required_context_refs including this ExecPlan, the target ExecPlan, the final verify note, and the latest authoritative review summary`
  `PY`

Acceptance:
- Every target has a new `artifacts/reviews/*_xhigh_*` evidence chain on today's repository state.
- New findings are recorded without code repair.

### 5) Produce the matrix, answer policy questions, and close via maintainer LOOP
Deliverables:
- A final matrix note under `artifacts/verify/` containing at least:
  - target
  - historical closeout reviewer tier
  - fresh `xhigh` result
  - whether new findings appeared
  - finding severity
  - key artifact refs
  - implication for default reviewer policy
- Explicit answers to:
  - whether low/medium-closed features stay clean under fresh `xhigh`
  - whether `medium` is sufficient as the standard escalation layer
  - whether the default policy can be fixed as `FAST + low` baseline, `medium` escalation, `STRICT / xhigh` exception only
- Maintainer LOOP node evidence and stable closeout alias for this audit plan.

Commands:
- `sed -n '1,260p' artifacts/verify/20260308_xhigh_revalidation_matrix_v0.md`
- `sed -n '1,220p' artifacts/loop_runtime/by_execplan/<stable_execplan_id>/MaintainerCloseoutRef.json`
- `git status --short`

Acceptance:
- The matrix is auditable and tied to fresh review artifacts.
- The maintainer LOOP session reaches closeout on the audit itself.
- No system code is modified in this wave.

## Testing plan (TDD)
This is an audit-only wave, so there are no new implementation tests and no code repair loop. Instead:
- `test_node` replays existing deterministic contract/profile checks against current head.
- `implement_node` is a no-op evidence step recording that no code changes were made by design.
- `verify_node` records the final matrix note plus any rerun verification logs/notes.
- contamination is avoided because the wave does not inject test overlays or modify real Toolbox/Incubator content; it only writes audit artifacts under `artifacts/**`.

## Decision log
- 2026-03-08: treat this as a fresh-state audit, not a repair wave; findings are recorded but not fixed here.
- 2026-03-08: authoritative scope is the final settled state only; superseded intermediate reviewer rounds may inform context but must not be re-opened as if still live.
- 2026-03-08: use a newly materialized maintainer LOOP session for the audit itself to prove current mainline can still maintain/close without hidden thread memory.
- 2026-03-08: run fresh `gpt-5.4-xhigh` across all three groups so the policy conclusion is based on one reviewer tier on one current repo state.

## Rollback plan
- Remove this audit plan and its generated audit artifacts if the wave must be discarded:
  - `docs/agents/execplans/20260308_xhigh_revalidation_matrix_v0.md`
  - `artifacts/reviews/20260308_xhigh_revalidation_*`
  - `artifacts/verify/20260308_xhigh_revalidation_matrix_v0.md`
  - the audit run directory under `artifacts/loop_runtime/by_key/<run_key>/`
  - the stable closeout alias for this audit under `artifacts/loop_runtime/by_execplan/<stable_execplan_id>/`
- Verify rollback with:
  - `git status --short`

## Outcomes & retrospective (fill when done)
- Completed:
- Verification:
- Fresh xhigh matrix:
- Policy conclusion:
- Residual risks:
- Follow-on recommendation:
