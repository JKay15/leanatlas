# LOOP_WAVE_EXECUTION_CONTRACT v0.1 (Wave A)

This contract defines the execution meta-loop for delivering one Wave.

## 0) Assurance level policy (FAST/LIGHT/STRICT)

Wave execution MUST declare `assurance_level`:
- `FAST`: draft/exploration; completion is not blocked by AI-review evidence gate.
- `LIGHT`: default development; deterministic gates are mandatory, AI review can be policy-triggered.
- `STRICT`: auditable completion; PASS requires complete AI-review evidence chain.

STRICT completion gate (hard rule):
- if `assurance_level = STRICT` and `final_decision.state = PASSED`, evidence MUST include:
  - `ai_review_prompt_ref`
  - `ai_review_response_ref`
  - `ai_review_summary_ref`

Design principle:
- only strict/publication-grade outcomes pay full review cost; low-risk iterations stay efficient.

Maintainer-loop requirement for non-trivial system changes:
- `ExecPlan -> graph_spec -> test node -> implement node -> verify node -> AI review node -> LOOP closeout`
- For maintainer work on system surfaces, this sequence must be materialized as a LOOP graph before routine implementation begins.
- manual closeout is exceptional only.
- If AI review cannot complete after bounded tooling attempts, closeout may use `TRIAGED_TOOLING` with persisted attempt evidence instead of silently skipping review.
- A maintainer `LOOP closeout` node must still execute after `AI review` reaches `FAILED` or `TRIAGED`; use graph-level closeout materialization rather than leaving the run in implicit `UPSTREAM_BLOCKED`.
- That closeout node must not improve the terminal class decided by `AI review`; it records the same terminal state (`PASSED|FAILED|TRIAGED`) rather than overriding it.

## 1) Execution meta-loop states

Execution track for the Wave process:
- `PENDING`
- `RUNNING`
- `AI_REVIEW`
- `PASSED`
- `FAILED`
- `TRIAGED`

Allowed transitions:
- `PENDING -> RUNNING`
- `RUNNING -> AI_REVIEW`
- `AI_REVIEW -> RUNNING`
- `AI_REVIEW -> PASSED`
- `AI_REVIEW -> FAILED`
- `AI_REVIEW -> TRIAGED`

Mandatory edge-to-reason mapping:
- `PENDING -> RUNNING` requires `WAVE_START`
- `RUNNING -> AI_REVIEW` requires `IMPLEMENTATION_SUBMITTED_FOR_REVIEW`
- `AI_REVIEW -> RUNNING` requires `REVIEW_REPAIR_LOOP`
- `AI_REVIEW -> PASSED` requires `REVIEW_PASS`
- `AI_REVIEW -> FAILED` requires `REVIEW_NON_RETRYABLE_FAULT` or `REVIEW_INVALID_VERDICT`
- `AI_REVIEW -> TRIAGED` requires one of:
  - `REVIEW_BUDGET_EXHAUSTED`
  - `REVIEW_STAGNATION`
  - `REVIEW_UNRESOLVED_BLOCKER`
  - `REVIEW_WALL_CLOCK_BUDGET_EXHAUSTED`

Hard rules:
- Direct `RUNNING -> PASSED` is forbidden.
- `HUMAN_REVIEW` is asynchronous evidence and MUST NOT block the execution track.

## 2) Strict AI review I/O contract

AI_REVIEW verdict enum: `PASS | REPAIRABLE | UNRESOLVED_BLOCKER | NON_RETRYABLE`

Each AI review record MUST include:
- `engine` (for example `codex exec review`)
- `prompt_ref`
- `response_ref`
- `verdict`
- `confidence` in `[0,1]`
- `finding_fingerprint` (stable hash)
- `findings[]` with `finding_id`, severity, repairable flag, and evidence refs
- `history_context_refs` (evidence refs for prior review history provided to current reviewer)

Provider-routing evidence (required for every Wave run):
- `agent_provider_id`
- `resolved_invocation`
- `instruction_scope_refs`

Hard rule:
- the resolved provider invocation must match configured provider selection (for example `codex_cli -> codex exec review`).
- provider-invoked reviewers MUST be launched with repo-root context and instruction scope visibility (`instruction_scope_refs` must include active `AGENTS.md` chain references).
- maintainer AI review nodes MUST execute through a deterministic reviewer runner rather than ad-hoc shell closeout.
- review scope MUST be a non-empty file list rooted under the repository.
- raw provider capture and LOOP closeout MUST be separate stages: `stdout/stderr/response artifacts -> CanonicalReviewResult -> REVIEW_RUN|REVIEW_SKIPPED`.
- reviewer launch MUST freeze a visibility/context pack before invocation. That pack MUST include:
  - normalized `scope_paths`
  - `scope_fingerprint`
  - `instruction_scope_refs`
  - `required_context_refs`
  - provider routing / semantic-closeout expectations
- the visibility/context pack MUST also freeze an `observation_policy` section so later auditors can see exactly which waiting rules governed the attempt.
- `instruction_scope_refs` MUST cover the active `AGENTS.md` chain induced by the scoped files and `required_context_refs`; arbitrary unrelated `AGENTS.md` files are insufficient.
- maintainer session materializers must derive that active chain from frozen maintainer inputs, including `execplan_ref`, not only mutable review scope files.
- maintainer materializers SHOULD canonicalize `instruction_scope_refs` to that active chain before hashing run identity so unrelated extra refs cannot fork a review session.
- `required_context_refs` MUST be a non-empty file-scoped list of immutable context evidence needed by the reviewer (for example active ExecPlan, relevant contracts/tests, latest verify evidence).
- provider-invoked reviewers MUST use bounded execution (hard timeout + idle timeout). Unbounded reviewer invocations are forbidden.
- reviewer runners MUST distinguish transport idle from semantic idle. Stderr warnings or other non-semantic chatter MUST NOT reset the semantic-idle clock.
- semantic progress is limited to canonical response growth, provider event-stream growth on declared semantic streams, or deterministic extraction/materialization of a terminal assistant response.
- canonical response growth on declared semantic activity paths MUST also suppress transport-idle timeout; a reviewer that is steadily extending `response_ref` is active, not silent.
- subjective early termination is forbidden. Maintainers must not stop a live reviewer attempt merely because it feels slow while the provider is still within the frozen observation policy.
- high-thinking provider modes are expected to be slow; operator impatience is not a valid closeout reason.
- minimum observation window for `codex_cli` is 600 seconds.
- two-minute impatience aborts are invalid for `codex_cli`; short waits of that class are policy violations unless an explicitly different frozen provider contract says otherwise.
- default `codex_cli` observation policy:
  - 60-minute hard timeout
  - 10-minute transport-idle default
  - 20-minute semantic-idle default
- if semantic progress does not occur within the configured semantic-idle timeout, the runner MUST terminate the provider attempt as `SEMANTIC_IDLE_TIMEOUT` and treat the round as unresolved tooling triage rather than waiting indefinitely.
- reconnect-aware grace is allowed only as a bounded extension (default cap: max 5 reconnect events); reconnect grace must not remove hard-timeout fallback.
- if reviewer execution times out/stalls, the run MUST persist command evidence (`timed_out=true`, `exit_code=124`, stdout/stderr refs) and treat that review round as unresolved blocker (`UNRESOLVED_BLOCKER` / `REVIEW_UNRESOLVED_BLOCKER`) instead of hanging.
- partial or streamed `response_ref` bytes do not override timeout/stale classification; if the provider times out or the scoped inputs drift, the round MUST NOT be accepted as `REVIEW_RUN` merely because the response file is non-empty.
- if any file in `scope_paths` is deleted, renamed, or otherwise becomes unreadable during execution, the runner MUST still record the round as `STALE_INPUT` with attempt evidence rather than aborting before closeout evidence is written.
- timeout command evidence MUST be materialized as `evidence.timeout_command_span` with fields:
  - `timed_out=true`
  - `exit_code=124`
  - `stdout_path`
  - `stderr_path`
- if final reason is `REVIEW_WALL_CLOCK_BUDGET_EXHAUSTED`, `evidence.timeout_command_span` is mandatory (machine-checkable blocking gate).
- if `REVIEW_REPAIR_LOOP` occurs, terminal closure MUST come from a later AI review round.
- reusing the same `prompt_ref` or `response_ref` across distinct AI review rounds is forbidden.
- every maintainer AI review attempt MUST materialize a canonical review payload that validates against `CanonicalReviewResult.schema.json`.
- response artifact MUST exist and be non-empty before `REVIEW_RUN`.
- provider JSON event stream may be used as a fallback semantic source only when the runner deterministically extracts a terminal assistant message and materializes the canonical `response_ref` from it.
- acceptable fallback extraction shapes include terminal assistant message carriers such as `event.message.assistant`, `event.item.assistant_message`, and `event.item.agent_message`; non-assistant `final_message` / `last_message` fallbacks are forbidden.
- if the provider exits without a non-empty canonical response and without an acceptable terminal assistant event, the runner MUST classify the attempt as `NO_TERMINAL_EVENT` (or stricter invalid-response subtype) and MUST NOT accept the round as `REVIEW_RUN`.
- scope fingerprint mismatch makes the attempt stale and unusable for closeout; the stale attempt must be recorded, not silently accepted.
- scope observed stamp mismatch also makes the attempt stale, including mutate-and-restore rewrites that restore the original content before process exit.
- reviewer attempts and their command evidence MUST be persisted under `artifacts/reviews/`.
- bounded failed attempts may terminate as `TRIAGED_TOOLING`, but only with append-only attempt evidence showing why no valid `response_ref` was accepted.

Reviewer-memory consistency evidence (required for every Wave run):
- `review_history_consistency` summary with:
  - `contradiction_count`
  - `potential_nitpick_count`
  - `contradiction_refs`
  - `nitpick_refs`

Hard rule:
- if contradiction/nitpick flags exist, those refs must be persisted and passed into later review rounds through `history_context_refs`.

Reviewer concurrency and supersession policy (hard rule):
- For the same `review_scope_key`, at most one reviewer invocation may be `RUNNING` at any time.
- Preemptive dynamic composition is allowed only via explicit supersession record:
  - `superseded_review_round_id`
  - `superseding_review_round_id`
  - `supersede_reason`
  - `supersede_created_at_utc`
- If a superseded reviewer later returns output, that output must still be ingested and marked as one of:
  - `APPLIED`
  - `NOOP_ALREADY_COVERED`
  - `REJECTED_WITH_RATIONALE`
- Terminal closeout (`PASSED|FAILED|TRIAGED`) requires `review_supersession_reconciliation` evidence that every started reviewer round is reconciled (no orphan reviewer outputs).

Review principles for AI auditor:
- Evidence-first: every finding must cite `file:line` and evidence refs.
- Consistency: avoid contradicting prior accepted findings without explicit correction rationale.
- Non-nitpick discipline: style-only remarks without correctness impact are informational, not blocking.
- Determinism preference: when uncertain, request deterministic gate/test addition rather than ad-hoc judgment.

## 3) Deterministic transition function (review -> next state)

Given review verdict + budgets + stagnation counters:
- `PASS -> PASSED` with reason `REVIEW_PASS` (only when no higher-precedence condition triggers)
- `REPAIRABLE and retry budget remains -> RUNNING`
- `REPAIRABLE and retry budget exhausted -> TRIAGED (`REVIEW_BUDGET_EXHAUSTED`)`
- `UNRESOLVED_BLOCKER -> TRIAGED` with reason `REVIEW_UNRESOLVED_BLOCKER` (unless higher-precedence stagnation triggers)
- `NON_RETRYABLE -> FAILED` with reason `REVIEW_NON_RETRYABLE_FAULT` (unless higher-precedence stagnation triggers)
- `same finding_fingerprint repeats >= 2 -> TRIAGED (`REVIEW_STAGNATION`)`

Deterministic precedence (highest first):
1. `same finding_fingerprint repeats >= 2` (`REVIEW_STAGNATION`)
2. `NON_RETRYABLE`
3. `UNRESOLVED_BLOCKER`
4. wall-clock budget exhausted (`REVIEW_WALL_CLOCK_BUDGET_EXHAUSTED`)
5. `REPAIRABLE` branch
6. `PASS`

The transition function must be deterministic and replayable from persisted review inputs.

## 4) Strict stop and budget policy

Default budgets for the Wave execution meta-loop:
- `max_ai_review_rounds = 8`
- `max_same_fingerprint_rounds = 2` (fixed in Wave A; not tunable)
- `max_wave_wall_clock_minutes = 120`

Exit conditions:
- terminal only when state in `{PASSED, FAILED, TRIAGED}`
- while state is non-terminal, the loop must continue
- `REPAIRABLE` verdict cannot terminate as `PASSED`
- `STRICT` + `PASSED` cannot terminate without required AI-review evidence refs.

## 5) Required evidence artifacts

Each Wave execution run MUST persist:
- iteration log with ordered review records
- transition trace with reason codes
- final decision record
- review evidence links (`prompt_ref`, `response_ref`, findings evidence)

Trace consistency invariants:
- transition trace must start at `PENDING -> RUNNING`
- transition trace must be contiguous (`transitions[i].to == transitions[i+1].from`)
- count of `AI_REVIEW -> *` transitions must equal `len(iterations)`
- last transition `(to, reason_code)` must equal `final_decision.(state, reason_code)`

Blocking gate (hard rule):
- Wave completion evidence MUST pass a deterministic blocking gate that checks:
  - schema conformance (`WaveExecutionLoopRun.schema.json`)
  - trace consistency invariants above
  - budget/terminal coherence
  - DirtyTreeGate (`dirty_tree` evidence must be present)
  - if final state is `PASSED` and `in_git_repo=true`, worktree must be clean before pass (commit or ignore generated files first)
  - if `in_git_repo=false`, `dirty_tree` MUST be canonical: `disposition=NO_GIT_CONTEXT`, `is_clean=true`, zero counts, empty status sample, `head_commit=null`
  - review-history consistency + `history_context_refs` propagation
- if any blocking check fails, run output MUST be `ERROR` (no success claim).

Suggested artifact paths:
- `.cache/leanatlas/loop_runtime/by_key/<run_key>/wave_execution/*`
- `artifacts/loop_runtime/by_key/<run_key>/wave_execution/*`

## 6) Codex execution hook (non-normative example)

Recommended AI review invocation:
- `codex exec review -o <path> "$(cat <prompt-file>)"`

The persisted `prompt_ref` still points at `<prompt-file>` even when the provider CLI consumes prompt text positionally rather than via a prompt-file flag.

Equivalent `codex exec` wrappers are allowed if they preserve the required review evidence fields.
