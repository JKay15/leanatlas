# tools/index

This directory stores LeanAtlas **local indexes / state truth sources (machine-readable)**.

Important:
- These files are not the Lean correctness truth source (the Lean environment is).
- They are the truth sources for the **library growth system / gates / retrieval policy**, used to keep the system maintainable and auditable.

## Files

- `gc_state.json`
  - Seeds GC lifecycle state truth source.
  - Records each Seed’s state: `active / quarantined / archived`.
  - Constraints:
    - V0 default changes only this state file; it does not move/rename Seed `*.lean` files (to avoid breaking module paths).
    - Schema: `docs/schemas/GCState.schema.json`
    - Contract: `docs/contracts/GC_STATE_CONTRACT.md`

Planned additions (future phases):
- `toolbox_index.json` (Toolbox retrieval entrypoints + domain metadata)
- `seed_index.json` (Seeds retrieval entrypoints + domain metadata)
- `deprecations.json` (Toolbox compat/deprecation mapping)
