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

Maintainer orchestration requirement:
- Non-trivial maintainer work MUST materialize a maintainer LOOP graph before implementation and close through the same execution system.
- Required maintainer sequence: `ExecPlan -> graph_spec -> test node -> implement node -> verify node -> AI review node -> LOOP closeout`
- Maintainer Python helpers MUST expose an upfront session materialization path (for example `materialize_maintainer_session(...)`) that freezes `graph_spec`, `run_key`, scope/context refs, and append-only node journal evidence before `implement node` work begins.
- Preferred maintainer path: use a higher-level session facade (for example `MaintainerLoopSession`) that materializes once, advances node results, and closes through the same object rather than stitching together post-hoc summaries.
- Maintainer session run identity MUST include active ExecPlan contents, not merely the `execplan_ref` pathname.
- `execplan_ref` MUST stay disjoint from `scope_paths`; once a maintainer session is materialized, the frozen ExecPlan cannot also be treated as a mutable implementation target.
- Maintainer session run identity is defined by frozen scope selection and immutable context evidence; it MUST NOT depend on the mutable bytes of the scoped files that `test node` / `implement node` are expected to edit.
- Re-materializing the same maintainer session inputs MUST reuse the same run identity/session artifacts rather than failing on volatile fields such as timestamps.
- post-hoc `GraphSummary` alone is insufficient evidence that maintainer work actually executed through LOOP; session and node-journal artifacts must exist before closeout.
- Maintainer session helpers SHOULD publish a deterministic derived progress sidecar (`MaintainerProgress.json`) so humans can see completed, pending, and current nodes without manually parsing append-only journals.
- SDK-facing helpers may return host-local bundle sidecars, but the embedded `graph_spec` must remain a canonical `LoopGraphSpec`.
- Maintainer closeout helpers MUST use a deterministic reviewer runner for provider-invoked AI review.
- That reviewer runner MUST require a non-empty review scope file list and emit append-only attempt evidence.
- That reviewer runner MUST also materialize a visibility/context pack before provider launch, including normalized `instruction_scope_refs`, `required_context_refs`, scope fingerprint, and provider semantic-closeout expectations.
- The visibility/context pack MUST include an explicit `observation_policy` object recording the active hard timeout, transport idle timeout, semantic idle timeout, and minimum observation window.
- That reviewer runner MUST separate raw provider capture from LOOP closeout by materializing a canonical review payload before any `REVIEW_RUN` or `REVIEW_SKIPPED` decision.
- The canonical review payload MUST validate against `CanonicalReviewResult.schema.json`.
- raw provider stdout/stderr are audit evidence only; maintainer LOOP closeout MUST consume the canonical review payload rather than matching provider event shapes directly.
- That reviewer runner MUST enforce a semantic-idle gate in addition to transport idle; non-semantic stderr chatter must not keep the closeout attempt alive.
- `instruction_scope_refs` MUST cover the active `AGENTS.md` chain induced by the review scope and `required_context_refs`.
- Maintainer session materialization MUST validate `instruction_scope_refs` against the active `AGENTS.md` chain induced by `execplan_ref` as well as `scope_paths` and `required_context_refs`; callers must not be able to freeze an incomplete chain.
- Maintainer session materialization MUST canonicalize `instruction_scope_refs` to the active `AGENTS.md` chain; unrelated extra `AGENTS.md` refs must not fork `run_key`.
- `required_context_refs` MUST be non-empty for maintainer AI review nodes.
- `required_context_refs` MUST stay disjoint from `scope_paths` because maintainer run identity must be anchored in immutable context evidence, not the mutable bytes of files being edited.
- Maintainer session run identity MUST include the frozen `graph_spec` contents, not just `change_id` and mutable artifact paths.
- The stale-input guard MUST reject both content drift and observed-scope drift across review execution, including mutate-and-restore scope rewrites that end with the original bytes.

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
