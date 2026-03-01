# ExecPlan: Phase3 — GCGate V0 (Seeds GC loop: roots → reachability → mark/sweep + domain logical clocks)

Goal: keep `Incubator/Seeds` from growing without bound, without “timestamp mysticism”.
V0 core: **domain progress (logical clock) + reachability (tracing GC)**.

V0 safety floor: **do not move files, do not delete `.lean` files; only mutate `tools/index/gc_state.json`.**

Reuse notes: `docs/reuse/GC_REUSE.md` (import-graph / Nix gcroots / tracing-GC patterns).

## 0) Inputs / outputs (every term explained)

### Inputs

- **Snapshot**
  - meaning: a GC run is bound to a fixed repo state + toolchain (commit / `lean-toolchain` / Lake env).
  - purpose: determinism (same Snapshot + same state → same GCPlan/GCReport).

- **ProblemState (`Problems/<slug>/State.json`)**
  - meaning: lifecycle state truth source for a problem workspace.
  - V0 uses it for only two things:
    1) root selection (domain-layered selection of active problems)
    2) domain progress clock (count problems with `ever_succeeded=true`)

- **GC roots (root set)**
  - meaning: entrypoints that are always considered live (tracing GC root set).
  - sources (V0):
    1) `Toolbox/**` modules (Toolbox is always a root)
    2) active Problems, via `Problems/<slug>/State.json`, domain-layered: per domain pick `1×ACTIVE + 2×SUCCESS + 1×TRIAGED`
    3) explicit pinned seeds (version-controlled): `tools/gc/roots.json: pinned_seeds`
    4) local pins (gitignored): `tools/gc/gcroots/*` symlink roots

- **import edges (from source imports)**
  - meaning: if module A `import`s B, add an edge A → B.
  - providers (by reliability):
    1) `import-graph` FromSource parser (default in V0)
    2) fallback: text scan `import ...` (lower confidence; must be flagged in report)

- **policy (thresholds/strategy)**
  - meaning: thresholds used for this GC run; must be recorded in `GCPlan.policy` and `GCReport.policy`.

Default thresholds (V0, measured in domain logical clock units):
- `grace_new_seed = 2`
- `quarantine = 8`
- `archive = 24`
- `revival_grace = 4`
- `revival_pending_window = 6`

- **mode (run permission)**
  - meaning: what side effects are allowed.
  - rules:
    - `OPERATOR`: propose only (no side effects)
    - `MAINTAINER`: allow apply (mutates gc_state truth source)

### Outputs

- `GCPlan.json`
  - meaning: a machine-readable proposal. Each action must carry evidence fields. Fields must be extensible (do not hard-enum decisions).

- `GCReport.json` + `GCReport.md`
  - meaning: an audit report (machine + human). Must clearly record roots, reachability provider, thresholds, and summary.

- patch (apply phase only)
  - meaning: modifications to `tools/index/gc_state.json` (rollbackable).

## 1) Why Propose → Apply is mandatory
This is the engineering version of tracing GC “mark/sweep”:

- **Propose = mark (read-only)**
  - can run frequently (nightly/weekly or automation)
  - outputs plan + report for audit

- **Apply = sweep (side effects)**
  - V0 side effects are small: only update the state file
  - must be MAINTAINER-only to avoid unaudited damage

## 2) Propose (automatable, no side effects)

### 2.1 Snapshot (freeze the world)
Record:
- repo_root, tool provider (import-graph / fallback), root sources

### 2.2 Root computation (domain-layered)
From `Problems/*/State.json`, read deterministically:
- `domain.domain_id`
- `status ∈ {ACTIVE,SUCCESS,TRIAGED,...}`
- `last_run.run_id` and `counters.attempts` (deterministic recency proxy; do not use filesystem mtime)

Per domain select:
- `1×ACTIVE` (most “recent”)
- `2×SUCCESS`
- `1×TRIAGED`

Use these problems’ entrypoints as roots:
- `Problems.<slug>.Spec / Proof / Cache` (if modules exist)

### 2.3 Import graph (local modules only)
Enumerate local `.lean` modules:
- `LeanAtlas/**` + `Problems/**`

Use `import-graph` FromSource to extract direct imports.
Example:

```bash
lake env lean --run scripts/import_edges_from_source.lean -- LeanAtlas/Toolbox/Imports.lean
```

Filter edges to the local module set and build an adjacency list.

### 2.4 Reachability mark (tracing)
Run BFS/DFS from roots (toolbox modules + active problem modules + pinned seeds).
Mark Seeds with:
- `reachable=true/false`
- `reached_by=[pinned|toolbox|active_problems]` (at least one)
- `use_hits` (V0: if reached by active problems, treat as a use signal)

### 2.5 Domain clock (logical time)
- `domain_clock[domain_id] = count(problems with ever_succeeded=true)`
For each seed:
- `introduced_at_clock` (fixed when first added to gc_state)
- `last_used_clock` (updated when reached/used)
- `staleness = domain_clock - last_used_clock`

### 2.6 Decide (generate actions)
Rules:
- `pinned`: force `active` (even if previously archived/quarantined)
- `used & quarantined`: `activate` + `revival_grace_until_clock`
- `used & archived`: two-stage revival:
  - stage1: `quarantine` + `revival_pending`
  - stage2: second independent hit within the window → `activate`
- `unreachable & stale`:
  - if `active` and `staleness>=quarantine` → `quarantine`
  - if `quarantined` and `staleness>=archive` → `archive`
- if `age < grace_new_seed`: protect young generation (avoid thrash)

## 3) Apply (MAINTAINER only)

### 3.1 Precheck (hard gate)
- CLI must be `--mode MAINTAINER`
- V0 patch scope (CI should enforce):
  - allow: `tools/index/gc_state.json` + artifact dirs
  - forbid: moving/deleting any `.lean` file

### 3.2 Execute actions (V0: state-only)
Allowed actions:
- `activate` / `quarantine` / `archive` / `meta`

All effects are written only to:
- `tools/index/gc_state.json`

## 4) TDD (real workflow + extreme sequences)

Core profile:
- schema: GCPlan/GCReport positive + negative fixtures
- determinism: same input → same output (canonical JSON)
- safety: apply requires MAINTAINER; V0 forbids delete/move

Nightly / soak:
- `gc_unreachable_and_stale_quarantine`
- `gc_pinned_roots_never_collected`
- `gc_archived_two_stage_revival`
- `gc_sequence_pressure`: multiple propose/apply interleavings; ensure state machine does not drift into nonsense
