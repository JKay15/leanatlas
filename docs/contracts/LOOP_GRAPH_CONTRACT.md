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
- `GraphSummary.json`
- merge/arbitration decisions (when applicable)
- node decision references linked by `node_id` and `run_key`

## 5) Determinism requirements

- Scheduler/merge/arbitration decisions must be replayable from persisted inputs.
- Conflict resolution must record winner rule and evidence path.
