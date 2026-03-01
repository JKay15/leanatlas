# GC_GATE_CONTRACT v0.4

This contract defines LeanAtlas **GCGate (Incubator Seeds GC)**:
- how we quarantine/archive Seeds under `LeanAtlas/Incubator/Seeds/**`
- while staying auditable, rollbackable, and automation-friendly

Key ideas:
- GC is **not wall-clock based**; it is triggered by a **domain logical clock** (domain progress count).
- GC uses a **two-stage deletion philosophy**: quarantine/archive first; delete is disabled by default.

Seeds lifecycle state source of truth:
- `docs/contracts/GC_STATE_CONTRACT.md` (file: `tools/index/gc_state.json`).

---

## 1) Baseline: reuse mature GC concepts (do not reinvent)

Seeds GC is not memory GC, but the abstraction is almost identical:
- a set of objects (Seeds)
- a reference relation (uses/imports)
- a root set (Toolbox + active problems + pinned Seeds)

We reuse classic patterns:
- Nix GC roots: roots → reachability decides liveness
- Git GC grace period: do not delete immediately when something becomes unreachable

LeanAtlas mapping (V0):
- **Roots**:
  1) `LeanAtlas/Toolbox/**` (always live)
  2) active Problems (via `Problems/<slug>/State.json`, domain-layered selection)
  3) pinned Seeds (`tools/gc/roots.json`, plus optional local `tools/gc/gcroots/` symlink roots)

- **Reachability edges** (deterministic signals):
  1) `uses_value/uses_type` (from AttemptLog / telemetry)
  2) module imports (prefer import-graph FromSource; fallback to conservative `import` text scan)

- **Mark / Sweep**:
  - Mark: propose (read-only) on a fixed snapshot
  - Sweep: apply state changes (V0: only update `gc_state.json`)

- **Generational**:
  - Seeds = nursery (many are short-lived)
  - Toolbox = tenured (retirement is via deprecation/compat, not Seeds GC)

- **Barrier events**:
  - each attempt’s `uses_value` record is treated as a deterministic “use signal” for last-used metadata.

---

## 2) V0 scope

V0 covers:
- target objects: `LeanAtlas/Incubator/Seeds/**`
- actions: `keep` / `quarantine` / `archive`
- outputs: `GCReport.{json,md}` (required), `GCPlan.json` (recommended)
- safety: default **no delete**, and no physical file moves/renames

V0 explicitly does not cover:
- automatic refactors/splits to avoid GC (only suggestions)
- Toolbox retirement (Toolbox uses deprecations/compat lifecycle)

---

## 3) Terms (strong definitions)

- **Seed**: a tool unit under `Incubator/Seeds` (identified by a stable `seed_id`; see `GC_STATE_CONTRACT`).
- **Domain**: an ontology label (MSC2020/LOCAL). Used for bucketing and logical clocks.
- **Domain progress count**: within the same domain, how many distinct `problem_slug`s have advanced since last use.
  - V0 default clock: count of problems with `ever_succeeded=true` in that domain.
- **Staleness**: domain progress count since last use.
- **Quarantine**: isolated (lower retrieval priority; recoverable).
- **Archive**: strongly isolated (hidden by default; recoverable with staged revival).
- **Roots**: entrypoints treated as live.
- **Reachability**: marked live if reachable from roots along deterministic edges.
- **Mark**: compute reachability on a fixed snapshot (no side effects).
- **Sweep**: apply actions (state update only in V0).

---

## 4) Active problem roots (domain-layered selection)

Truth source:
- `Problems/<slug>/State.json` (see `PROBLEM_STATE_CONTRACT`).

GCGate must not infer state by “scanning Reports”; it must read `State.json`.

### 4.1 Default domain-layered selection (V0)

Bucket problems by `domain.domain_id` (unknown → `UNKNOWN`).
For each domain select:
- `K_active_per_domain = 1` most-recent ACTIVE
- `K_success_per_domain = 2` most-recent SUCCESS
- `K_triaged_per_domain = 1` most-recent TRIAGED

Rationale:
- TRIAGED is included to align with “grace period”: recently-triaged work should not cause freshly-produced Seeds to be swept immediately.

### 4.2 Deterministic definition of “most recent”

Use deterministic fields:
- prefer `State.json.last_run.run_report_path` and the run_id embedded in the filename (recommended sortable format)
- fallback tie-break: `State.json.counters.attempts` (monotone)

Filesystem mtime is not allowed as a decision input.

---

## 5) Input: GCPlan (recommended)

File: `GCPlan.json`
Schema: `docs/schemas/GCPlan.schema.json`

### 5.1 Required top-level fields
- `version: string`
- `policy: object` (must record thresholds explicitly)
- `actions: array`

Recommended `policy` fields (V0 defaults; not hard enums):
- `mark_strategy: "tracing"`
- `age_clock: "domain_progress_problems"`
- `two_phase_delete_enforced: true`
- `active_problem_roots`:
  - `strategy: "per_domain_layered"`
  - `k_active_per_domain: 1`
  - `k_success_per_domain: 2`
  - `k_triaged_per_domain: 1`
  - `unknown_domain_bucket: "UNKNOWN"`
- `thresholds` (domain logical clock units):
  - `grace_new_seed: 2`
  - `quarantine: 8`
  - `archive: 24`
  - `revival_grace: 4`
  - `revival_pending_window: 6`
- `reachability_sources: ["uses_value","imports"]`

### 5.2 Required fields per action
- `seed_id: string` (stable id; must match GC_STATE seed_id rules)
- `action: string` (must express keep/quarantine/archive semantics)
- `evidence: object` (must be auditable)

Recommended evidence fields:
- `domain_id`
- `last_used_problem`
- `last_used_runs[]`
- `domain_progress_count_since_last_use`
- `reachable` and `reached_by[]`

---

## 6) Output: GCReport (required)

Files:
- `GCReport.json` + `GCReport.md`

Schema:
- `docs/schemas/GCReport.schema.json`

Required top-level fields:
- `version`
- `policy`
- `actions[]` (each must include seed/action/evidence)
- `safety` (must include `two_phase_delete_enforced=true`)
- `summary`

---

## 7) V0 safety rules (cannot be broken)

Apply phase must be MAINTAINER-only.

V0 allowed write targets:
- `tools/index/gc_state.json` (truth source)
- `tools/gc/roots.json` and optional `tools/gc/gcroots/**` (roots)
- `artifacts/gc/**` and `.cache/leanatlas/**` (audit artifacts)

V0 forbidden:
- touching `LeanAtlas/Toolbox/**` or `LeanAtlas/Compat/**`
- moving/renaming/deleting any `*.lean` file

Default: delete is disabled. If enabled in a future version, it must:
- be two-stage (quarantine/archive first)
- be fully recorded in plan/report with rollback guidance

All changes must land as a patch/PR (auditable, rollbackable).

---

## 8) Revival policy (no silent revivals)

Revival is a control-plane state transition and must be auditable.

Trigger:
- A reliable `uses_value` hit for a Seed whose `gc_state != active`.

Rules:
- Propose must emit an explicit revival action in `GCPlan.actions`.
- GCReport must record the revival action and the evidence.
- Silent state flips are forbidden.

Default revival actions (V0):
- if `quarantined` is hit:
  - `quarantined → active` (single hit is enough)
  - set `revival_grace_until_clock` to prevent immediate re-quarantine

- if `archived` is hit:
  - staged revival:
    1) first hit: `archived → quarantined` + `revival_pending=true`
    2) second independent hit within `revival_pending_window` (different `problem_slug` or different `run_id`):
       - `quarantined → active` + set revival grace

Retrieval ladder integration:
- `active`: normal priority
- `quarantined`: de-prioritized unless explicitly included
- `archived`: hidden unless explicitly included

---

## 9) TDD matrix (must cover real workflow)

Core profile:
- GCPlan/GCReport schema fixtures (positive/negative)
- patch-scope safety: forbid Toolbox touches
- no-rename: V0 must not move/rename any `.lean`
- determinism: same input → same canonical JSON output

Nightly profile:
- tracing reachability keeps live Seeds
- pinned roots never collected
- unreachable+stale → quarantine (main path)
- grace period prevents thrash
- revival staged behavior works

Soak profile:
- long sequences propose/apply/revert across many domains and Seeds
- artifacts don’t explode; `scripts/clobber.sh` restores a clean state
