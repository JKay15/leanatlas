# LIBRARY_GROWTH_CONTRACT v0.1

This contract defines the **public interface shape** of LeanAtlas’s Library Growth System:
- tool deposition
- dedup
- promotion
- seeds GC

Important:
- V0.1 freezes only **report artifact shapes** and **auditable evidence fields for gates**.
- Algorithms (hashing, definitional equality checks, subsumption) are intentionally left flexible in V0 and are tightened later via dedicated contracts.

---

## Terms (strong definitions)

- **candidate**: a declaration (decl) that a maintenance action is trying to add/move/remove.
- **seed**: a candidate tool in `Incubator/Seeds` (searchable, importable, collectible).
- **toolbox**: an official tool in `Toolbox` (stable interface, long-term reusable).
- **dedup**: decide relationships between a candidate and the existing library (duplicate/equivalent/subsumes/subsumed/conflict).
- **promotion**: promote a Seed (or external bundle) into Toolbox.
- **gc**: apply a policy that moves Seeds into quarantine/archive (and possibly deletion in future), following two-stage safety.

---

## Required reports (must exist)

Every run must produce the following reports (both md + json forms should be supported; json is used by CI and automations):

1) `DedupReport`
2) `PromotionReport`
3) `GCReport`

Each report must validate against its JSON Schema in `docs/schemas/*.schema.json`.

---

## Minimal field constraints (v0.1)

### DedupReport (Dedup gate)
Must contain:
- `candidates[]`
- for each candidate entry:
  - `decision`: string (open-world, not hard-enum; recommended values below)
  - `evidence`: at least one evidence source (e.g. `type_hash_match`, `isDefEq_check`, `name_collision`, `search_hits`)
  - `related[]`: 0+ related decls (suspected duplicate, subsumer/subsumed, alternative, etc.)

Recommended `decision` values (not a hard enum):
- `UNIQUE`
- `DUPLICATE`
- `SUBSUMED_BY_EXISTING`
- `SUBSUMES_EXISTING`
- `CONFLICT`
- `NEEDS_HUMAN`

### PromotionReport (Promotion gate)
Must contain:
- `promotion_targets`: candidates to be promoted
- `gates[]`: per-gate results (`passed` + evidence refs)
- `decision`: final gate decision (`passed` + string reason code)

V0.1 minimal required gate entries (shape only; criteria tightened later):
- `env_existence_check`
- `type_check`
- `dedup_gate_present` (must reference a DedupReport)
- `rollback_plan_present`

### GCReport (GC / isolation)
Must contain:
- `policy`: policy summary (string or object)
- `actions[]`: per-seed actions (keep/quarantine/archive/delete… as open strings)
- `safety`: auditable safety statement

---

## Hard floors (cannot be broken)

- Any promotion must pass DedupGate first, and PromotionReport must reference that evidence.
- Any delete must follow quarantine/archive first (two-stage), and must be traceable in GCReport.
- Report JSON must be canonical (stable field order; stable array ordering) to support diff/regression.
