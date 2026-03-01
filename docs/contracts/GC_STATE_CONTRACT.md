# GC_STATE_CONTRACT v0.2

This contract defines `tools/index/gc_state.json`: the **Seeds GC lifecycle state source of truth** (machine-readable).
It drives:
- retrieval ladder ranking/visibility for Seeds
- PromotionGate/GCGate eligibility
- automations (unattended quarantine/archive/restore proposals)

Important:
- This is not the Lean correctness truth source (the Lean environment is).
- This is the **control plane** of the library-growth system.

---

## 0) Terms (strong definitions)

- **Seed**: a candidate tool module under `LeanAtlas/Incubator/Seeds/**`.
  - Typically 1 `*.lean` file corresponds to 1 Seed module.

- **seed_id**: stable identifier for a Seed.

  **V0.2 rule (enforced):** `seed_id` must be the **Lean module name**.
  Example: `LeanAtlas.Incubator.Seeds.Algebra.Group.Basic`.

  Rationale (aligned with the real Lean ecosystem interface):
  1) `import` resolves modules by module name; module name is derived from the file path by Lean’s rules.
  2) import-graph FromSource returns module `Name`s and its CLI expects module names.
  3) LSP/environment indexing also keys on module names.

  Forbidden:
  - using repo-relative paths (`LeanAtlas/Incubator/Seeds/.../Basic.lean`) as `seed_id`.
    - paths are physical locations; module names are the identity.

- **GC state**: lifecycle visibility/availability status of a Seed.

- **Roots**: the set of objects considered “must be live” (see GCGate contract and `tools/gc/roots.json` / `tools/gc/gcroots/**`).

---

## 1) File location and schema

- Path: `tools/index/gc_state.json`
- Schema: `docs/schemas/GCState.schema.json`

All fields must satisfy schema.
JSON must be canonical:
- indent=2
- sorted keys
- UTF‑8

---

## 2) Top-level fields

### 2.1 `version: string` (required)
Format version of gc_state.
Constraint: `0.x` (e.g. `0.2`).

### 2.2 `seeds: object` (required)
Map: `seed_id -> state_record`.
Constraints:
- keys are module names starting with `LeanAtlas.`
- each record must include at least `state`

---

## 3) state_record fields

Constraint: `state` is the only mandatory hard field. Other fields are open-world (extensible).

### 3.1 `state: "active" | "quarantined" | "archived"` (required)
Semantics (V0 fixed):

- `active`
  - normal state
  - eligible as default candidates in the Seeds layer of retrieval

- `quarantined`
  - isolation state (stage 1 of the two-stage deletion philosophy)
  - source files remain; explicit imports still work (V0 does not move files)
  - retrieval should **de-prioritize** it (avoid noise)

- `archived`
  - stronger isolation
  - default: excluded from retrieval unless explicitly requested (`include_archived=true` / deep search)
  - source files remain (V0 no delete) for rollback/audit

### 3.2 `path_hint: string|null` (optional, strongly recommended)
Repo-relative source file path, e.g.
`LeanAtlas/Incubator/Seeds/Algebra/Group/Basic.lean`.

Purpose:
- helps tooling locate/edit the file without re-deriving module→path
- allows tests to ensure the record points to an existing module

Constraint:
- if present, it must match Lean’s module↔path rule.

### 3.3 `aliases: object|null` (optional)
Maps historical `seed_id` values (old module names) to the current `seed_id`.
Purpose:
- smooth renames/refactors without breaking historical AttemptLog/bench references.

Recommended structure:
- key: old module name
- value: new/current module name

### 3.4 `reason: object|null` (optional)
Why this Seed is in this state.
Open fields, but should avoid non-reproducible data.

Recommended fields:
- `code`: e.g. `unreachable_and_stale` / `pinned_root` / `manual_quarantine`
- `policy_ref`: a GCPlan/GCReport path or hash
- `evidence_refs[]`: artifact paths

### 3.5 `refs: object|null` (optional)
External references (PR id, automation run id, report path).

### 3.6 `domain: object|null` (optional)
Domain hint (MSC2020/LOCAL). Not authoritative; can be regenerated.

### 3.7 `notes: string|null` (optional)
Human note; must not be used by gate logic.

---

## 4) Update rules (V0 must enforce)

### 4.1 Who may edit
- OPERATOR: must not edit `tools/index/gc_state.json`.
- MAINTAINER: may edit only via:
  1) `GCGate.apply` (apply GCPlan actions)
  2) `RestorePlan.apply` (explicit restore, must produce a report)

### 4.2 Allowed diff surface
V0 default changes only:
- the state file itself (`tools/index/gc_state.json`)

V0 forbids:
- moving/renaming any Seed `*.lean` file

### 4.3 Auditability (evidence chain)
Every change must be traceable to:
- a `GCReport` / `RestoreReport` (machine + human)
- a rollbackable patch/PR

---

## 5) Runtime semantics

### 5.1 Retrieval ladder
- `active`: normal Seeds layer
- `quarantined`: only enters a low-priority Seeds layer; RetrievalTrace must record this
- `archived`: excluded by default; only allowed when explicitly requested

### 5.2 PromotionGate
- Seeds with `state != active` are **ineligible for promotion**.
- To promote, restore to active first (via an auditable restore plan).

### 5.3 GCGate
- `gc_state.json` is the only truth source mutated by apply.
- If telemetry shows a real use (`uses_value HIT`) of a quarantined/archived Seed:
  - propose must mark it as `revival_candidate=true`
  - apply (MAINTAINER) must produce a restore patch (`state → active`) following the staged revival rules (see `GC_GATE_CONTRACT`).

Hard discipline: no silent revivals.

---

## 6) Minimum TDD matrix

Core profile:
- schema fixtures (positive/negative)
- canonical JSON check for the file
- `seed_id` must be a module name, and must map to an existing `*.lean` file
- apply patch scope: GCGate V0 apply may only touch `gc_state.json` and artifacts

Nightly profile:
- quarantine then reuse triggers an explicit restore proposal and an apply-able restore patch
