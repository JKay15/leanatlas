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

Graph builder rule:
- graph payload MUST remain schema-valid against `LoopGraphSpec.schema.json`.
- host metadata sidecar is allowed for local composition helpers (for example resource manifests or composition notes), but that sidecar is not part of the canonical graph payload and must not be mixed into `graph_spec`.
- for maintainer work, canonical graph materialization must happen before implementation begins; `GraphSpec.json` must exist before `implement node` work is accepted.
- maintainer orchestration must also persist a visible session sidecar (`MaintainerSession.json`) and append-only node journal (`NodeJournal.jsonl`) so observers can tell that work is proceeding through the declared LOOP graph rather than being annotated only at closeout time.
- maintainer orchestration should also publish a derived progress sidecar (`MaintainerProgress.json`) showing completed, pending, and current node ids so observers do not need to parse the journal to understand in-flight status.
- default merge rule for `SERIAL | PARALLEL | NESTED | BARRIER` is all-pass.
- if a node sets `allow_terminal_predecessors=true`, it may execute once all predecessor nodes are terminal, even when they did not all pass. This is intended for closeout/evidence-sink nodes.
- `allow_terminal_predecessors` is only valid on sink nodes with at least one incoming edge, and those incoming edges must be `SERIAL | PARALLEL | NESTED | BARRIER`; it must not be attached to non-sink, `RACE`, or `QUORUM` nodes.
- `GraphSummary.final_status` must preserve the worst admitted terminal class for sink paths; a closeout node using `allow_terminal_predecessors=true` must not mask upstream `FAILED` or `TRIAGED` outcomes as `PASSED`.

## 5) Determinism requirements

- Scheduler/merge/arbitration decisions must be replayable from persisted inputs.
- Conflict resolution must record winner rule and evidence path.
