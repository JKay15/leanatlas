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
- `assurance_level` (`FAST | LIGHT | STRICT`, default `FAST`)

Routing/evidence field emission rule:
- optional routing fields MUST be omitted when unknown/empty; SDK MUST NOT emit `null` or empty-array placeholders that violate schema types.
- if `review_history` is provided (including `[]`), SDK MUST persist deterministic history artifacts and return `review_history_ref`.
- if `review_plan` is provided and non-empty, `run(...)` MUST execute `RUNNING <-> AI_REVIEW` rounds until terminal and emit `WaveExecutionLoopRun` evidence in `response.trace_refs`.

The SDK is a facade over LOOP runtime contracts; it must not redefine semantics.

Post-onboarding default preference requirement:
- bounded user-facing LOOP defaults MAY be persisted at `.cache/leanatlas/onboarding/loop_preferences.json`
- committed helper surface for those defaults:
  - `build_default_review_policy(...)`
  - `build_default_tiered_review_policy(...)`
  - `build_preference_record(...)`
  - `default_preference_artifact_path(...)`
  - `load_preference_record(...)`
  - `write_preference_record(...)`
  - `resolve_effective_preferences(...)`
- supported user-facing assurance presets:
  - `Budget Saver`
  - `Balanced`
  - `Auditable`
- supported reviewer tier policies:
  - `LOW_ONLY`
  - `LOW_PLUS_MEDIUM`
- `Budget Saver` is the committed default preset for the current mainline path.
- `FAST + low` is the default reviewer path for the current mainline path.
- `LOW_PLUS_MEDIUM` is the committed default reviewer tier policy for the current mainline path.
- `medium` is the standard bounded escalation tier.
- `medium` is a bounded escalation for small-scope high-risk core logic.
- `STRICT / xhigh` is exceptional and must not be treated as the normal default path.
- preset storage is advisory and post-onboarding only; later runs may override the stored defaults without mutating the persisted preference artifact

Layering rule:
- `serial(...)`, `parallel(...)`, and `nested(...)` are LOOP core composition helpers.
- `OPERATOR`, `MAINTAINER`, and `worktree` policies are host/workflow adapters layered on top of that core.
- SDK/contracts must not redefine native parallelism or nested execution in LeanAtlas role-specific terms.

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
- `MaintainerProgress.json` SHOULD distinguish ordinary runnable work from bookkeeping-only closeout by exposing:
  - `bookkeeping_pending_node_ids`
  - `current_node_mode` (`RUNNABLE | BOOKKEEPING_CLOSEOUT`)
- Maintainer closeout MUST also publish a stable execplan-addressable closeout alias:
  - `artifacts/loop_runtime/by_execplan/<stable_execplan_id>/MaintainerCloseoutRef.json`
- That stable closeout alias MUST preserve at least:
  - `execplan_ref`
  - `run_key`
  - `summary_ref`
  - `final_status`
  - `updated_at_utc`
  - `session_created_at_utc`
  - `session_created_at_epoch_ns`
- `MaintainerSession.json`, `MaintainerProgress.json`, and `close_maintainer_session(...)` return summaries MUST expose `closeout_ref_ref` so ExecPlans can cite settled-state LOOP closeout without embedding a run-key-specific `GraphSummary.jsonl` path in the plan body and perturbing `execplan_hash`.
- Maintainer closeout must reject stale frozen inputs before settled-state closeout. At minimum, it must reject stale execplan bytes before settled-state closeout, refuse to rewrite the stable closeout alias from an out-of-date session, and refuse to let an older same-plan session overwrite a newer stable closeout ref.
- legacy sessions missing `required_context_hash` or `instruction_chain_hash` must be rematerialized before closeout.
- Maintainer `ai_review_node` evidence MUST also freeze the reviewed scope using `scope_fingerprint` plus `scope_observed_stamp`.
- Maintainer closeout must reject mutate-and-restore scope drift after `ai_review_node`; the current reviewed scope must still match the `scope_observed_stamp` captured when `ai_review_node` was recorded.
- SDK-facing helpers may return host-local bundle sidecars, but the embedded `graph_spec` must remain a canonical `LoopGraphSpec`.
- Maintainer closeout helpers MUST use a deterministic reviewer runner for provider-invoked AI review.
- That reviewer runner MUST require a non-empty review scope file list and emit append-only attempt evidence.
- That reviewer runner MUST also materialize a visibility/context pack before provider launch, including normalized `instruction_scope_refs`, `required_context_refs`, scope fingerprint, and provider semantic-closeout expectations.
- The visibility/context pack MUST include an explicit `observation_policy` object recording the active hard timeout, transport idle timeout, semantic idle timeout, and minimum observation window.
- That reviewer runner MUST separate raw provider capture from LOOP closeout by materializing a canonical review payload before any `REVIEW_RUN` or `REVIEW_SKIPPED` decision.
- The canonical review payload MUST validate against `CanonicalReviewResult.schema.json`.
- raw provider stdout/stderr are audit evidence only; maintainer LOOP closeout MUST consume the canonical review payload rather than matching provider event shapes directly.
- That reviewer runner MUST enforce a semantic-idle gate in addition to transport idle; non-semantic stderr chatter must not keep the closeout attempt alive.
- Maintainer helper surfaces MUST expose deterministic review-acceleration planners such as:
  - `partition_review_scope_paths(...)`
  - `merge_partition_scope_paths(...)`
  - `build_pyramid_review_plan(...)`
  - `build_review_orchestration_graph(...)`
  - `build_review_orchestration_bundle(...)`
- `partition_review_scope_paths(...)`, `merge_partition_scope_paths(...)`, and `build_pyramid_review_plan(...)` are planning aids only. They do not by themselves produce terminal closeout evidence.
- `build_review_orchestration_graph(...)` compiles the schema-valid executable LOOP review graph payload only.
- `build_review_orchestration_bundle(...)` compiles the executable LOOP review graph plus deterministic sidecar routing metadata and is the authoritative artifact for per-node reviewer-routing/audit metadata.
- `graph_spec` may still persist coarse orchestration metadata needed for graph identity or merge policy (for example strategy/reconciliation summaries under `merge_policy.review_orchestration`), but it MUST NOT replace the bundle sidecar as the authoritative source for per-node reviewer routing.
- `build_review_orchestration_bundle(...)` MUST return a machine-readable `stage_manifest` containing one entry per executable orchestration node, including non-review orchestration nodes such as `review_intake` and `finding_dedupe`; if callers later materialize bundle artifacts, that returned `stage_manifest` becomes the authoritative persisted routing sidecar. Consumers MUST be able to join each entry back to `graph_spec.nodes` via its stable `node_id`. Each entry MUST include at least:
  - `node_id`
  - `stage_id`
  - `review_tier`
  - `agent_provider_id`
  - `scope_paths`
  - `scope_fingerprint`
  - `partition_id` when the node is partition-scoped
- `stage_manifest.scope_paths` duplicate checks MUST be evaluated on canonical repo-relative file identities, not raw caller spellings; alias forms such as `foo.py` and `./foo.py` MUST be rejected as duplicates when they resolve to the same repo file.
- Reviewer-launching nodes MUST include `agent_profile` when provider/profile routing selected a concrete profile for that node.
- Non-review orchestration nodes that do not launch a reviewer MUST omit `agent_profile` rather than emit `null` placeholders.
- Authoritative orchestration bundles MUST reject blank routing or scope metadata. At minimum, compilation MUST fail when any of the following are blank:
  - top-level `agent_provider_id`
  - top-level `full_scope_fingerprint`
  - top-level `effective_scope_fingerprint`
  - any reviewer-launching stage `agent_profile`
  - any partition `scope_fingerprint`
  - `final_integrated_closeout.scope_fingerprint`
- `build_review_orchestration_graph(...)` and `build_review_orchestration_bundle(...)` MUST validate authoritative scope fingerprints against the live repository bytes under the supplied `repo_root`; compilation MUST NOT trust caller-supplied fingerprint strings for:
  - top-level `full_scope_fingerprint`
  - top-level `effective_scope_fingerprint`
  - any partition `scope_fingerprint`
  - `deep_partition_followup.scope_fingerprint` when `deep_partition_followup.partition_ids` is non-empty
  - `final_integrated_closeout.scope_fingerprint`
- Authoritative replay/bundle compilation must also reject stale fingerprint metadata rather than trusting caller-supplied strings that no longer match the selected scope.
- `strategy_plan.strategy_fingerprint` MUST match the canonical hash of the authoritative strategy-plan content that executable orchestration artifacts actually consume; replayed or hand-authored narrowing metadata MUST be rejected if it carries a stale `strategy_fingerprint`.
- `strategy_plan.strategy_fingerprint` MUST cover the complete top-level provenance surface consumed by authoritative closeout artifacts, including `strategy_id`, `selected_partition_ids`, `effective_scope_paths`, `effective_scope_fingerprint`, and `effective_scope_source`; replayed plans must not be able to forge those top-level fields without invalidating the fingerprint.
- `strategy_plan.strategy_fingerprint` MUST NOT fork only because replayed plans mutate ignored metadata that the executable bundle does not consume, such as `strategy_plan.partitions[*].partition_group`, `deep_partition_followup.scope_source`, or no-followup-only inert deep-stage fields like `deep_partition_followup.agent_profile` / `deep_partition_followup.scope_fingerprint` when `deep_partition_followup.partition_ids=[]`.
- Authoritative replay/bundle compilation must reject stale `strategy_fingerprint` values before graph/bundle materialization.
- For the compiled pyramid-review helper surface, `strategy_plan.strategy_id` MUST remain `review.pyramid_partition.v1`; authoritative bundle compilation must reject replayed or hand-authored plans that relabel the strategy while still using the same compiler.
- In the compiled orchestration graph, the deep follow-up stage is materialized via nested child-review nodes and the final integrated closeout sink is the only closeout-authoritative stage.
- That final integrated closeout sink MUST remain executable after post-dedupe advisory stages (for example deep follow-up nodes) reach terminal non-pass states; later integrated closeout auditing must not be skipped merely because a post-dedupe advisory stage failed.
- In explicit no-followup runs, `finding_dedupe` is still a hard gate; authoritative closeout must remain blocked when reconciliation itself ends `FAILED` or `TRIAGED`.
- Fast partition scan nodes still gate `finding_dedupe`; a terminal non-pass fast scan blocks reconciliation and therefore blocks authoritative closeout until that fast-stage failure is repaired or rerun.
- `build_pyramid_review_plan(...)` SHOULD accept a narrowed follow-up partition set and/or merged `effective_scope_paths` so later stages can reflect real staged narrowing instead of forcing a full-scope re-review.
- `fast_partition_scan.partition_ids` MUST preserve the canonical `strategy_plan.partitions` order exactly for the chosen subset; replayed or hand-authored plans must not redefine the frozen fast-stage order, even if downstream deep/effective/final metadata is reordered consistently to match.
- `strategy_plan.full_scope_paths` MUST preserve canonical repo-relative file order; replayed or hand-authored plans must not fork `strategy_fingerprint` or intake-stage provenance by permuting an otherwise identical full-scope file set.
- `strategy_plan.partitions` itself MUST preserve the canonical helper-derived partition order; replayed or hand-authored plans must not permute the partition list and then rewrite fast/deep/effective/final lineage to match.
- `strategy_plan.partitioning_policy` MUST preserve the helper-authored partitioning policy shape exactly. In authoritative replay plans, `group_by` MUST remain `TOP_LEVEL_SCOPE_PREFIX` and `max_files_per_partition` MUST remain the helper-authored integer chunk size; string/bool lookalikes such as `"2"` or `true` are not authoritative replays.
- `strategy_plan.partitions.*.scope_paths` MUST preserve canonical repo-relative file order within each partition; replayed or hand-authored no-followup plans must not reverse files inside a partition and then mirror that reordered lineage into `finding_dedupe` / final integrated closeout scope.
- If callers replay or hand-author a narrower fast stage, `deep_partition_followup.partition_ids` MUST stay within the frozen `fast_partition_scan.partition_ids` subset; deep follow-up nodes must not be materialized for partitions that were never scanned in the current fast stage.
- `strategy_plan.partitions` entries MUST carry unique `partition_id` values and non-empty `scope_paths`; authoritative bundle compilation must reject duplicate routing ids or empty fast-stage reviewer scopes before graph/bundle materialization.
- `strategy_plan.stages` MUST contain exactly one each of `fast_partition_scan`, `deep_partition_followup`, and `final_integrated_closeout`; authoritative bundle compilation must reject duplicate or unknown `stage_id` entries that the compiler would otherwise ignore.
- `strategy_plan.stages` MUST preserve the canonical helper-authored stage order exactly; replayed or hand-authored plans must not permute otherwise equivalent stage descriptors and fork `strategy_fingerprint`/integrated closeout provenance.
- Each authoritative stage descriptor MUST preserve the helper-authored stage descriptor shape exactly; replayed or hand-authored plans must not change ignored static policy metadata such as `review_tier`, `finding_policy`, `selection_policy`, or `closeout_eligible` and still expect bundle compilation to accept them.
- `strategy_plan.partitions.*.scope_paths` MUST form an exact disjoint cover of `full_scope_paths`; authoritative bundle compilation must reject overlapping partition files, repeated files inside a partition, or omitted full-scope files that would leave part of the frozen fast-stage lineage unreviewed.
- When a narrowed follow-up selection is known, the deep follow-up stage and the final integrated closeout stage MUST reflect that narrowed effective scope deterministically.
- `strategy_plan.selected_partition_ids` MUST match `deep_partition_followup.partition_ids` exactly; replayed or hand-authored plans must not be able to forge a conflicting top-level selected-partition summary.
- When explicit `followup_partition_ids` are supplied to `build_pyramid_review_plan(...)`, the resulting `selected_partition_ids` / `deep_partition_followup.partition_ids` MUST preserve the frozen `fast_partition_scan.partition_ids` order exactly; helper output must not lexicographically reorder `part_100+` partition ids.
- `strategy_plan.partitions[*].partition_id` numeric prefix MUST remain zero-padded so lexical node ordering stays aligned with the frozen helper partition order even after `part_100+`.
- `strategy_plan.partitions[*].partition_id` values MUST preserve the canonical helper-derived routing ids exactly, including zero-padded numeric prefixes and helper slug formatting; replayed or hand-authored plans must not relabel partitions to malformed ids such as `part_1_*` or ids containing characters outside the helper-safe slug alphabet.
- `strategy_plan.partitions` MUST also match the helper-generated partition boundaries exactly for the declared `partitioning_policy`; replayed or hand-authored plans must not repartition a top-level group under canonical-looking ids and still expect authoritative replay to accept the graph/bundle lineage.
- When `deep_partition_followup.partition_ids` is non-empty, both `strategy_plan.selected_partition_ids` and `deep_partition_followup.partition_ids` MUST preserve the frozen `fast_partition_scan.partition_ids` order exactly; replayed or hand-authored plans must not reorder the selected partitions, even if the narrowed deep/effective/final `scope_paths` are reordered consistently to match.
- When `deep_partition_followup.partition_ids` is non-empty, `deep_partition_followup.scope_paths` MUST stay within the selected partition lineage and MUST include at least one file from every selected partition; bundle compilation MUST reject silent widening or silent partition drop.
- When `deep_partition_followup.partition_ids` is non-empty, `deep_partition_followup.scope_paths` MUST also match the canonical selected partition lineage exactly; replayed or hand-authored plans must not reorder the narrowed deep/effective/final scope together away from the frozen partition-derived order.
- When `deep_partition_followup.partition_ids` is non-empty, `deep_partition_followup.scope_paths`, `effective_scope_paths`, and `final_integrated_closeout.scope_paths` MUST match exactly; replayed or hand-authored strategies MUST NOT widen the authoritative integrated closeout back to the full selected-partition union after the deep stage has narrowed scope.
- For every authoritative "`scope_paths` must match exactly" rule above, exactness is sequence-sensitive, not set-sensitive; replayed or hand-authored plans that reorder the same file set MUST be rejected because they fork deterministic lineage and `strategy_fingerprint`/bundle provenance.
- `strategy_plan.effective_scope_source` MUST match `final_integrated_closeout.scope_source`; replayed or hand-authored plans must not be able to forge a different top-level narrowing provenance string than the one the authoritative integrated closeout stage actually uses.
- `strategy_plan.effective_scope_source` / `final_integrated_closeout.scope_source` MUST use a canonical helper-authored provenance label:
  - `MERGED_SELECTED_PARTITIONS`
  - `FULL_SCOPE_AFTER_EMPTY_FOLLOWUP`
  - `INFERRED_FROM_EFFECTIVE_SCOPE`
  - `MANUAL_EFFECTIVE_SCOPE_OVERRIDE`
- `FULL_SCOPE_AFTER_EMPTY_FOLLOWUP` is only valid when `deep_partition_followup.partition_ids=[]`; replayed or hand-authored plans must not claim the empty-followup full-scope closeout label for any narrowed deep-stage lineage.
- When `deep_partition_followup.partition_ids` is non-empty, `final_integrated_closeout.scope_paths` MUST also stay within that same selected partition lineage; authoritative integrated closeout must not widen beyond what the staged narrowing actually selected.
- `effective_scope_paths`, `deep_partition_followup.scope_paths`, and `final_integrated_closeout.scope_paths` MUST NOT repeat the same repo file path more than once; authoritative lineage metadata must stay multiplicity-stable with the repository-byte fingerprints later consumed by review runners.
- If `effective_scope_paths` narrows inside a selected multi-file partition, the compiled deep follow-up node manifest MUST preserve that narrowed file subset in `scope_paths` while also retaining the original partition scope in dedicated audit fields:
  - `partition_scope_paths`
  - `partition_scope_fingerprint`
  - `scope_fingerprint_basis`
- `scope_fingerprint_basis` is required whenever the deep follow-up stage may replay a narrowed scope. Its allowed values and meanings are:
  - `REPO_FILE_BYTES`: `scope_fingerprint` is the repository-byte fingerprint of the exact file set listed in `scope_paths`
  - `PATH_SET`: `scope_fingerprint` is the deterministic hash of the narrowed `scope_paths` set itself, used when manual narrowing picks a subset of files inside a larger partition
- `PATH_SET` fingerprints MUST be order-insensitive across replayed or hand-authored partition serialization, and compiled deep-stage `scope_paths` for the same narrowed file set MUST stay canonically ordered in the authoritative stage manifest.
- Replaying helper-derived merged scope back into `build_pyramid_review_plan(...)` alongside the same `followup_partition_ids` MUST preserve the same provenance metadata and `strategy_fingerprint`; helper output replay must not fork semantically identical plans.
- If callers replay or hand-author a narrower fast stage, `build_review_orchestration_bundle(...)` sidecar metadata (for example `composition_notes.fast_partition_node_ids`) MUST stay aligned with the frozen `fast_partition_scan.partition_ids`; the bundle MUST NOT advertise fast-scan nodes that do not exist in the compiled `graph_spec`.
- In replayed or hand-authored fast-stage subsets, the `finding_dedupe` stage-manifest `scope_paths` / `scope_fingerprint` MUST freeze the actual `fast_partition_scan.partition_ids` lineage rather than the original full frozen scope; reconciliation metadata must not overstate which partitions were scanned in the current run.
- `build_pyramid_review_plan(..., followup_partition_ids=[])` MUST be valid and represent the clean-fast-scan/no-escalation path explicitly; callers must not be forced to omit the parameter to encode "nothing to escalate".
- `build_pyramid_review_plan(..., followup_partition_ids=[], effective_scope_paths=[])` MUST also be valid and represent the same explicit no-escalation path; the empty `effective_scope_paths=[]` input is shorthand for "keep the canonical full fast-scan scope" rather than a literal empty closeout scope.
- In that explicit no-escalation path, the deep follow-up stage may have empty `partition_ids` / `scope_paths`, but the final integrated closeout stage MUST remain present and must stay integrated over the canonical effective main scope.
- When `deep_partition_followup.partition_ids=[]`, `effective_scope_paths` and `final_integrated_closeout.scope_paths` MUST match the frozen `fast_partition_scan.partition_ids` lineage exactly. In helper-authored plans, an input `effective_scope_paths=[]` is shorthand for that canonical full-scope closeout rather than a literal empty scope. Replayed or hand-authored no-followup bundles MUST reject silent narrowing, silent widening, or scope replacement in the authoritative integrated closeout stage.
- Regardless of whether follow-up partitions are empty, `final_integrated_closeout.scope_paths` MUST match `effective_scope_paths` exactly and `final_integrated_closeout.scope_fingerprint` MUST match `effective_scope_fingerprint`; authoritative closeout must reject empty or widened scopes rather than compiling them.
- `strategy_plan.closeout_policy` MUST preserve the helper-authored closeout policy shape exactly; replayed or hand-authored plans must not inject extra policy keys or fork authoritative closeout provenance through ignored closeout metadata.
- `strategy_plan.closeout_policy.intermediate_rounds_are_advisory` and `strategy_plan.closeout_policy.requires_integrated_scope_closeout` MUST remain `true` in authoritative replay plans; bundle compilation must reject contradictory policy flags even when the compiled graph/bundle payload would otherwise stay unchanged.
- `build_review_orchestration_bundle(...)` MUST also return a machine-readable reconciliation contract for the `finding_dedupe` stage so later runners/auditors know which lineage record is required before authoritative integrated closeout.
- In helper-authored default staged-review strategies, `final_integrated_closeout.review_tier` MUST be `MEDIUM` and `final_integrated_closeout.agent_profile` MUST reuse the bounded medium escalation profile.
- `strategy_plan.bounded_medium_profile` MUST be non-empty and MUST be included in the authoritative `strategy_fingerprint` top-level provenance surface.
- In authoritative replay, `final_integrated_closeout.agent_profile` MUST match `strategy_plan.bounded_medium_profile` exactly when `final_integrated_closeout.review_tier = MEDIUM`.
- `strategy_plan.strict_exception_profile` MUST be non-empty and MUST be included in the authoritative `strategy_fingerprint` top-level provenance surface.
- Explicit exception plans MAY set `final_integrated_closeout.review_tier = STRICT`; when they do, `final_integrated_closeout.agent_profile` MUST reuse the explicit strict/xhigh exception profile instead of silently downgrading to medium.
- In authoritative replay, `final_integrated_closeout.agent_profile` MUST match `strategy_plan.strict_exception_profile` exactly when `final_integrated_closeout.review_tier = STRICT`.
- `STRICT / xhigh` remains an explicit exception path rather than the default integrated closeout tier.
- That reconciliation contract MUST include a stable `resource_id` locator for the reconciliation state, so later runners/auditors know where `finding_dedupe` lineage records live.
- That reconciliation contract MUST also pin:
  - `artifact_schema_ref = docs/schemas/ReviewSupersessionReconciliation.schema.json`
  - `authoritative_closeout_stage_id = final_integrated_closeout`
  - `late_output_disposition_enum = APPLIED | NOOP_ALREADY_COVERED | REJECTED_WITH_RATIONALE`
  - `required_fields` including `finding_key`, `finding_group_key`, and `scope_lineage_key`
- LOOP Python surfaces MUST expose a deterministic reconciliation runtime for staged review evidence:
  - `reconcile_review_rounds(...)`
  - `assert_review_reconciliation_ready(...)`
  - `persist_review_reconciliation(...)`
- `reconcile_review_rounds(...)` MUST consume the frozen review-orchestration bundle plus persisted review-round evidence and emit an authoritative finding ledger that validates against `ReviewSupersessionReconciliation.schema.json`.
- That authoritative finding ledger MUST settle every finding occurrence as `CONFIRMED`, `DISMISSED`, or `SUPERSEDED`; later closeout code MUST consume the reconciled ledger rather than raw advisory findings.
- That runtime MUST derive `scope_lineage_key` from the active source round scope path-set so unrelated partitions/scopes that reuse a source `finding_key` do not collapse into one authoritative finding group.
- That runtime MUST emit a deterministic `finding_group_key` so unrelated occurrences that share a source `finding_key` remain distinguishable across persistence/replay.
- Identical reconciliation inputs MUST yield identical immutable ledger payloads and ledger paths; append-only persistence journals may record wall-clock persistence time, but the immutable ledger itself must remain input-deterministic.
- The immutable reconciliation ledger MUST live at a run-key-independent artifact path; only the append-only persistence journal may stay scoped under `artifacts/loop_runtime/by_key/<run_key>/...`.
- That means the immutable reconciliation ledger lives outside any per-run `artifacts/loop_runtime/by_key/<run_key>/...` tree.
- Supersession records MUST be rejected when they claim that an older review round supersedes a newer one.
- `persist_review_reconciliation(...)` MUST materialize an immutable reconciliation ledger artifact plus an append-only journal, so later runtimes/auditors can replay the exact authoritative finding set instead of matching free-form reviewer text again.
- Partitioned or low-tier intermediate review rounds are acceleration aids; final `AI_REVIEW_CLOSEOUT` still requires an integrated closeout review over the effective main scope.
- `instruction_scope_refs` MUST cover the active `AGENTS.md` chain induced by the review scope and `required_context_refs`.
- Maintainer session materialization MUST validate `instruction_scope_refs` against the active `AGENTS.md` chain induced by `execplan_ref` as well as `scope_paths` and `required_context_refs`; callers must not be able to freeze an incomplete chain.
- Maintainer session materialization MUST canonicalize `instruction_scope_refs` to the active `AGENTS.md` chain; unrelated extra `AGENTS.md` refs must not fork `run_key`.
- `required_context_refs` MUST be non-empty for maintainer AI review nodes.
- `required_context_refs` MUST stay disjoint from `scope_paths` because maintainer run identity must be anchored in immutable context evidence, not the mutable bytes of files being edited.
- Maintainer session run identity MUST include the frozen `graph_spec` contents, not just `change_id` and mutable artifact paths.
- Maintainer `loop_closeout` remains a bookkeeping sink: it may record a terminal `FAILED` or `TRIAGED` closeout after upstream failure blocks `ai_review_node`, but it MUST preserve the resolved upstream terminal class and MUST NOT imply that AI review executed successfully.
- In blocked maintainer closeout paths, `reason_code="REVIEW_PASS"` (or any other success-implying AI review reason) MUST be rejected as misleading evidence.
- When `loop_closeout` is the only remaining bookkeeping sink after upstream failure/triage, `MaintainerProgress.json` MAY still expose it as the current/pending node, but it MUST simultaneously mark that state as bookkeeping closeout rather than ordinary runnable work.
- Recorded-graph replay that accepts legacy `GraphSummary.jsonl` rows missing `node_decisions[].executed` MUST rewrite the persisted summary to the current evidence shape before returning `summary_ref`.
- Maintainer recorded-graph replay MUST also preserve a journaled blocked `loop_closeout` as executed bookkeeping evidence rather than downgrading it back to synthesized `UPSTREAM_BLOCKED` in `GraphSummary.jsonl` / `NodeResults.json`.
- Legacy blocked-closeout replay compatibility is not limited to the summary row: if older persisted maintainer evidence still carries synthesized `UPSTREAM_BLOCKED` loop-closeout state, replay MUST upgrade `GraphSummary.jsonl`, `NodeResults.json`, and `graph/arbitration.jsonl` to the current bookkeeping-closeout evidence shape before returning success.
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
