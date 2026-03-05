# LOOP_RUNTIME_CONTRACT v0.1 (Wave A)

This contract defines the deterministic runtime model for one LOOP node/run.

## 1) Execution track (node runtime)

Execution track states:
- `PENDING`
- `RUNNING`
- `AI_REVIEW`
- `PASSED`
- `FAILED`
- `TRIAGED`

Required transition semantics:
- `PENDING -> RUNNING`
- `RUNNING -> AI_REVIEW`
- `AI_REVIEW -> RUNNING` (repair loop; only when issue is repairable and retry budget remains)
- `AI_REVIEW -> PASSED` (review accepted)
- `AI_REVIEW -> TRIAGED` (retry budget exhausted or unresolved blocker)
- `AI_REVIEW -> FAILED` (non-retryable runtime fault)

Hard rules:
- `HUMAN_REVIEW` MUST NOT appear in execution track as a blocking state.
- Loop-back `AI_REVIEW -> RUNNING` is mandatory in the model.

## 1.1) Assurance levels (token/time-aware policy)

LOOP-capable workflows MUST classify the required assurance level:
- `FAST`: exploratory/draft path; no hard AI-review completion gate.
- `LIGHT`: default engineering path; deterministic checks first, AI review is conditional.
- `STRICT`: auditable completion path; PASS claims require AI-review evidence chain.

Strict completion gate (hard rule):
- if `assurance_level = STRICT` and final claim is `PASSED`, artifacts MUST include:
  - `ai_review_prompt_ref`
  - `ai_review_response_ref`
  - `ai_review_summary_ref`

Policy intent:
- avoid unnecessary review cost in low-risk flows (`FAST`/`LIGHT`)
- fail-closed for publishable/auditable outcomes (`STRICT`)

## 2) Audit track (asynchronous, non-blocking)

Audit track states:
- `AUDIT_PENDING`
- `AUDIT_CONFIRMED`
- `AUDIT_FLAGGED_OPEN`
- `AUDIT_MITIGATED`
- `AUDIT_VERIFIED`
- `AUDIT_CLOSED`
- `AUDIT_ACCEPTED_RISK`

Hard rules:
- Audit track is post-hoc and non-blocking for execution completion.
- `PASSED` may coexist with `AUDIT_FLAGGED_OPEN`.
- If audit severity is `S1_CRITICAL` or unresolved `S2_MAJOR`, output must be tagged:
  - `PROMOTION_BLOCKED_BY_AUDIT`

## 3) Dynamic exception recovery defaults

Defaults for system-mode temporary recovery LOOPs:
- `max_dynamic_recovery_rounds_per_exception = 2`
- `max_dynamic_recovery_total_minutes = 45`
- `max_temp_graph_nodes = 6`
- `max_temp_graph_depth = 2`
- `max_parallel_branches = 3`
- `max_retry_per_node = 2`

Tuning band (system agent):
- rounds: `[1, 3]`
- total minutes: `[20, 90]`
- temp graph nodes: `[3, 10]`

Out-of-band tuning requires explicit user escalation.

## 4) Required run identity and evidence

Each run MUST contain:
- `run_key` (deterministic run identity)
- deterministic input/snapshot evidence
- instruction-resolution evidence
- per-attempt proposer/reviewer/judge outputs
- final decision and stop-rule evidence

Provider-invoked review runs MUST additionally persist:
- selected provider identifier (`agent_provider_id`)
- resolved invocation signature/command evidence
- instruction scope references (`instruction_scope_refs`) that include active `AGENTS.md` chain

Hard rule:
- provider routing is deterministic and replayable from persisted selection inputs (`agent_cmd` / `agent_profile` / `agent_provider` precedence).

## 5) Required artifacts (runtime layer)

Runtime artifacts SHOULD follow:
- `.cache/leanatlas/loop_runtime/by_key/<run_key>/...` (rebuildable)
- `artifacts/loop_runtime/by_key/<run_key>/...` (append-only audit)

## 6) Relationship to other contracts

- Graph composition: `docs/contracts/LOOP_GRAPH_CONTRACT.md`
- Resource arbitration: `docs/contracts/LOOP_RESOURCE_ARBITER_CONTRACT.md`
- Audit policy: `docs/contracts/LOOP_AUDIT_CONTRACT.md`
- MCP service interface: `docs/contracts/LOOP_MCP_CONTRACT.md`
- Python SDK surface: `docs/contracts/LOOP_PYTHON_SDK_CONTRACT.md`
