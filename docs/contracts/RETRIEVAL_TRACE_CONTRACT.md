# RETRIEVAL_TRACE_CONTRACT v0.3 (Phase 1 → Phase 4 compatible)

RetrievalTrace is an **audit log** of the domain-driven retrieval ladder.

Its purpose is not “make retrieval smarter”.
Its purpose is to make retrieval **auditable, benchmarkable, and rollbackable**.

---

## 1) Why `steps[*]` has mandatory fields

Each `steps[i]` MUST include:

- `step_index`
  - Stable ordering for diff/replay.
  - Timestamps are unstable; indices are replayable.

- `layer`
  - Which retrieval space produced candidates.
  - Needed for bench metrics (Recall@K, MRR) and to validate the ladder ordering (fast→slow).

- `action`
  - What was actually done (open-world but classifiable).
  - Without it, you cannot explain or tune the ladder.

- `result`
  - `HIT` / `MISS` / `ERROR`.
  - Needed to distinguish retrieval failure from build/verify failure.

---

## 2) `action` format: open-world, but with a minimal skeleton

`steps[].action` is an object:

- `family` (bounded enum; hard constraint)
  - `SEARCH`: search candidates (ripgrep/LeanSearch/loogle/env query, etc.)
  - `IMPORT`: attempt to add an import
  - `VALIDATION`: local env validation (exists/type checks)
  - `ATTEMPT`: attempt a candidate (lemma/tactic pattern)
  - `SUGGEST`: advisor suggestion (may not be executed)
  - `TOOLING`: tooling actions (MCP call, index build, file read, …)
  - `UNKNOWN`: fallback

- `code` (open string, e.g. `RG_SEARCH_DECL` / `ADD_IMPORT` / `ENV_LOOKUP`)
  - Convention: UPPER_SNAKE_CASE recommended, but not forced.

- `standard` (optional bool)
  - `true`: LeanAtlas-standard code
  - `false`: experimental/custom

- `label` / `ref` (optional)
  - Human-friendly label and/or a linkable reference.

---

## 3) `layer` values (the ladder layers)

`steps[].layer` is a bounded enum (Phase 1 stable minimal set; Phase 3/4 may extend):

- `ENVIRONMENT`
- `TOOLBOX_SAME_DOMAIN`
- `SEEDS_SAME_DOMAIN`
- `MATHLIB_SAME_DOMAIN`
- `DOMAIN_EXPAND`
- `EXTERNAL_SEARCH`

---

## 4) Budget integrity

- `budget.used_steps` MUST equal `len(steps)`.

Core tests enforce this.

---

## 5) Step index integrity

- `steps` must be sorted by `step_index`.
- `step_index` must start at 0 and be contiguous:
  - `steps[i].step_index == i`.

---

## 6) Phase 3 requirement: GC state observability (without schema changes)

If we introduce `gc_state.json` (`active/quarantined/archived`) but RetrievalTrace cannot show its effect on candidates, then GC becomes invisible and will rot.

We can achieve observability **without changing schema**, because `steps[].candidates[*]` and `steps[].chosen` are open objects.

### 6.1 Recommended fields for `candidates[*]`

For any layer’s candidates (especially Seeds):

- `id: string`
  - Stable identifier.
  - For Seeds/Toolbox: prefer module name or declaration name.

- `kind: string`
  - Example: `SEED_MODULE` / `TOOLBOX_MODULE` / `MATHLIB_DECL`.

- `score: number` (optional)
  - Retrieval score.

- `reason: string` (optional)
  - Short justification.

- `domain_id: string` (optional)
  - Domain bucket for bench grouping.

- `gc_state: string` (Phase 3 key field)
  - GC state read from `tools/index/gc_state.json`.
  - Must at least represent: `active/quarantined/archived/unknown`.

- `state_policy: string` (optional)
  - How the ladder treated this state, e.g. `DEFAULT_EXCLUDE`, `DEPRIORITIZE`, `INCLUDED_BY_FLAG`.

### 6.2 Recommended fields for `chosen`

`steps[].chosen` should include at least:
- `id`
- `kind`
- `gc_state` (when applicable)

### 6.3 Minimal auditable requirement (V0 strong requirement)

If a retrieval step includes or selects a Seed with `gc_state in {quarantined, archived}`:
- `candidates[*].gc_state` must be explicit, and
- AttemptLog must append a `GC_REVIVAL_HIT` event (see AttemptLog contract/ExecPlan).

---

## 7) Phase 4: domain routing / domain expansion observability (without schema changes)

With Domain Ontology MCP, RetrievalTrace must answer:

1) Which domain was selected, and what is the evidence?
2) Did we downgrade / refuse an unapproved new domain?

We keep the same stance: no schema change needed. Use `steps[].action` + open fields.

### 7.1 Recommended action codes
- `DOMAIN_ROUTE`
  - family: `TOOLING` (if MCP called) or `SEARCH` (if heuristic)
  - layer: `ENVIRONMENT`

- `DOMAIN_EXPAND_SET`
  - family: `TOOLING`
  - layer: `DOMAIN_EXPAND`

- `DOMAIN_ROOTS_SUGGEST`
  - family: `TOOLING`
  - layer: `ENVIRONMENT` (roots are a pruning prerequisite)

### 7.2 Recommended fields for route evidence

For `DOMAIN_ROUTE` step:

`candidates[*]` should include:
- `id` / `code` / `text`
- `score`
- `source_id`
- `evidence` (short text)

`chosen` should include:
- `domain_id` (coarse bucket)
- `msc_codes[]` (fine codes; may be empty)
- `confidence` (0..1)
- `fallback_used: bool`
- `new_domain_proposed: bool`
- `user_consent: "granted"|"denied"|"not_required"|"unknown"`

### 7.3 Guardrail: “new non-MSC local domain” must be auditable

If the system believes it must add a `local:*` domain:
- `DOMAIN_ROUTE.chosen.new_domain_proposed=true`
- If explicit user consent is not granted:
  - `user_consent="denied"` or `"unknown"`
  - and `fallback_used=true` (downgrade to `UNKNOWN` / no pruning)

This prevents silent contamination of the domain system.
