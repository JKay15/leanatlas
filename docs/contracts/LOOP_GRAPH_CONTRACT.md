# LOOP_GRAPH_CONTRACT v0.1 (Wave A)

This contract defines deterministic composition rules for LOOP graphs.

## 1) Supported edge kinds

Graph edge `kind` MUST be one of:
- `SERIAL`
- `PARALLEL`
- `NESTED`
- `RACE`
- `QUORUM`
- `BARRIER`

## 2) Node/run reference model

Each node MUST include:
- `node_id`
- `loop_id`

Optional:
- `run_key` (when node references a pre-existing run instance)
- `allow_terminal_predecessors` (node-local override for closeout/sink nodes that must still execute after upstream nodes end in `FAILED` or `TRIAGED`; only valid on sink nodes with at least one incoming edge)

Dedup rule:
- same semantic run (`run_key`) should be referenced, not duplicated.

## 3) Mode split: static vs dynamic exception recovery

`graph_mode` MUST be one of:
- `STATIC_USER_MODE`
- `SYSTEM_EXCEPTION_MODE`

Dynamic graph entry is allowed only when:
- current static flow cannot resolve an exception, and
- no documented remediation exists in active contracts/SOP/skills.

On dynamic recovery success:
- control returns to static flow.

On dynamic recovery failure:
- system agent may retry within budget or escalate to user.

## 4) Required outputs

Each graph run MUST emit:
- `GraphSummary.jsonl`
- merge/arbitration decisions (when applicable)
- node decision references linked by `node_id` and `run_key`
- each `node_decision` MUST record whether the node actually executed (`executed=true`) or was synthesized as a blocked placeholder (`executed=false`)
- replay/backfill of legacy `GraphSummary.jsonl` rows that predate `node_decisions[].executed` MUST upgrade the persisted summary to the current evidence shape rather than silently reusing the legacy row
- scheduler execution evidence (for example `scheduler.jsonl`) describing whether each batch actually ran in serial or parallel mode and the admitted parallel width
- nested lineage evidence (for example `nested_lineage.jsonl`) whenever `NESTED` edges are present

Graph builder rule:
- graph payload MUST remain schema-valid against `LoopGraphSpec.schema.json`.
- host metadata sidecar is allowed for local composition helpers (for example resource manifests or composition notes), but that sidecar is not part of the canonical graph payload and must not be mixed into `graph_spec`.
- for maintainer work, canonical graph materialization must happen before implementation begins; `GraphSpec.json` must exist before `implement node` work is accepted.
- maintainer orchestration must also persist a visible session sidecar (`MaintainerSession.json`) and append-only node journal (`NodeJournal.jsonl`) so observers can tell that work is proceeding through the declared LOOP graph rather than being annotated only at closeout time.
- maintainer orchestration must also publish a derived progress sidecar (`MaintainerProgress.json`) showing completed, pending, and current node ids so observers do not need to parse the journal to understand in-flight status.
- maintainer closeout must also publish a stable execplan-addressable alias (`MaintainerCloseoutRef.json`) so ExecPlans can cite settled-state LOOP closeout without embedding a run-key-specific `GraphSummary.jsonl` path in the plan body.
- session/progress/closeout-return surfaces should expose that alias as `closeout_ref_ref`.
- non-trivial maintainer sessions must also publish root-supervisor delegation artifacts before implementation begins:
  - `root_supervisor_skeleton.json`
  - `root_supervisor_delegation.json`
- those artifacts document the root supervisor kernel, delegated node ids, and the layered supervisor model for the active graph; they are not optional prose-only notes.
- `root_supervisor_skeleton.json` must identify the root-owned nodes, delegated node ids, the integrated closeout sink, and the stable path for any root-issued exception artifact.
- `root_supervisor_skeleton.json.root_nodes` must list only the root-owned nodes for the active graph; delegated nodes must remain outside that set.
- `root_supervisor_delegation.json` must preserve delegated node ids and mirror delegated execution evidence (`execution_path`, child execution refs, terminal state, reason code) as node results are recorded.
- manual/direct fallback is allowed only for a blocked subtree of delegated work and only when backed by a session-bound root-issued exception artifact for the active session; local blockage must not waive the whole non-trivial task.
- the stable session-bound root-issued exception artifact may append multiple bounded exception entries within one run, but overlapping `affected_node_ids` across entries are invalid.
- maintainer closeout must reject stale frozen inputs before rewriting the stable closeout ref alias; at minimum, stale execplan bytes must not be allowed to overwrite `MaintainerCloseoutRef.json`.
- legacy sessions missing `required_context_hash` or `instruction_chain_hash` must be rematerialized before closeout.
- stable closeout refs should preserve `session_created_at_utc` and `session_created_at_epoch_ns`, and an older same-plan session must not overwrite a newer stable closeout ref alias.
- if `ai_review_node` executes, its terminal journal evidence must freeze the reviewed scope using at least `scope_fingerprint` and `scope_observed_stamp`.
- maintainer closeout must reject mutate-and-restore scope drift after `ai_review_node`; current reviewed scope evidence must still match the frozen `scope_observed_stamp` captured when `ai_review_node` was recorded.
- default merge rule for `SERIAL | PARALLEL | NESTED | BARRIER` is all-pass.
- `PARALLEL` and `NESTED` are graph semantics first. They do not by themselves prove that runtime executed nodes concurrently; that fact must come from scheduler evidence.
- `graph_spec.scheduler.max_parallel_branches` defines the upper bound for true concurrent execution of dependency-free nodes. `max_parallel_branches=1` is a valid serial fallback even for graphs containing `PARALLEL` edges.
- if a node sets `allow_terminal_predecessors=true`, it may execute once all predecessor nodes are terminal, even when they did not all pass. For ordinary runnable work, those predecessor terminal states must come from actually executed nodes rather than synthesized `UPSTREAM_BLOCKED` placeholders.
- Maintainer bookkeeping `loop_closeout` is the explicit exception: replay/closeout bookkeeping may journal the sink after synthesized `UPSTREAM_BLOCKED` predecessors, provided it preserves the worst resolved upstream terminal class and does not mint success-implying AI review evidence.
- runtime MUST decide that distinction from explicit execution evidence, not by overloading free-form predecessor `reason_code` text.
- `allow_terminal_predecessors` is only valid on sink nodes with at least one incoming edge, and those incoming edges must be `SERIAL | PARALLEL | NESTED | BARRIER`; it must not be attached to non-sink, `RACE`, or `QUORUM` nodes.
- `GraphSummary.final_status` must preserve the worst admitted terminal class for sink paths; a closeout node using `allow_terminal_predecessors=true` must not mask upstream `FAILED` or `TRIAGED` outcomes as `PASSED`.
- When an `all-pass` fan-in (`SERIAL | PARALLEL | NESTED | BARRIER`) is blocked by multiple upstream non-pass terminal classes, runtime MUST preserve the worst upstream terminal class rather than the first lexicographic non-pass predecessor.
- root-issued exception artifacts must keep `affected_node_ids` within a proper subset of delegated nodes; they must not cover the full delegated node set for the run.

## 5) Determinism requirements

- Scheduler/merge/arbitration decisions must be replayable from persisted inputs.
- Conflict resolution must record winner rule and evidence path.
- If `NESTED` edges are used, runtime must persist a child-to-parent lineage record for each nested target so later reconciliation can distinguish nested execution from ordinary serial dependency.
