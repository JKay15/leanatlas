# LOOP_PYTHON_SDK_CONTRACT v0.1 (Wave A)

This contract freezes Python SDK-facing semantics before runtime implementation.

## 1) Canonical API surface (v1 draft)

Required callable surface:
- `loop(...)`
- `serial(...)`
- `parallel(...)`
- `nested(...)`
- `run(...)`
- `resume(...)`

Required routing parameters (provider-neutral):
- `agent_provider`
- `agent_profile`
- `instruction_scope_refs`
- `review_history`
- `review_plan` (optional deterministic reviewer rounds for local execution loop)
- `assurance_level` (`FAST | LIGHT | STRICT`, default `LIGHT`)

Routing/evidence field emission rule:
- optional routing fields MUST be omitted when unknown/empty; SDK MUST NOT emit `null` or empty-array placeholders that violate schema types.
- if `review_history` is provided (including `[]`), SDK MUST persist deterministic history artifacts and return `review_history_ref`.
- if `review_plan` is provided and non-empty, `run(...)` MUST execute `RUNNING <-> AI_REVIEW` rounds until terminal and emit `WaveExecutionLoopRun` evidence in `response.trace_refs`.

The SDK is a facade over LOOP runtime contracts; it must not redefine semantics.

## 2) Idempotency and retry behavior

- `run(...)` and `resume(...)` must support idempotency.
- Same semantic input should resolve to the same `run_key`.
- Repair loops must preserve attempt ordering and evidence chain.

## 3) Deterministic error model

SDK error envelope MUST include:
- `error_code` (stable identifier)
- `error_class` (typed category)
- `retryable` (boolean)
- optional human-readable message

## 4) Evidence return contract

SDK outputs must provide references for:
- run summary
- attempt log / decision evidence
- audit flags/remediation (if any)
- provider resolution evidence (`agent_provider`, resolved invocation signature)
  - SDK envelope field: `resolved_invocation_signature`
- reviewer history evidence (`review_history` summary and refs passed into later rounds)
  - for `review_history = []`, summary evidence still exists and reflects zero counts.
- when `assurance_level = STRICT` and completion claim is `PASSED`, include strict AI-review evidence refs:
  - `ai_review_prompt_ref`
  - `ai_review_response_ref`
  - `ai_review_summary_ref`

## 5) MCP alignment

SDK and MCP contracts must stay semantically aligned on:
- API group meanings
- idempotency requirements
- error envelope fields
- degradation behavior (local deterministic runner fallback)
