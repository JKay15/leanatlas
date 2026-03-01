# tools/gc

This directory is the entrypoint for **Seeds GC (collection loop)**.

Design principle:
- reuse mature GC abstractions (roots → reachability → mark/sweep)
- but in V0 the default action is **state-only**: do not move/delete `.lean` files

---

## Entry script: `gc.py`

### 1) `propose` (anyone can run; read-only analysis)

Inputs:
- `tools/index/gc_state.json` (Seeds lifecycle state source of truth)
- `Problems/*/State.json` (domain progress clock + active-problem root selection)
- `tools/gc/roots.json` + `tools/gc/gcroots/*` (pinned roots)
- local import edges:
  - prefer `import-graph` FromSource parsing
  - fallback to conservative text scanning

Outputs (under `--out-root`):
- `GCPlan.json`: proposed state transitions (with evidence)
- `GCReport.json/.md`: summary + policy + roots + reachability

Command:

```bash
uv run --locked python tools/gc/gc.py propose \
  --repo-root . \
  --out-root .cache/leanatlas/gc/propose \
  --mode OPERATOR
```

`propose` must not mutate any truth sources.

### 2) `apply` (MAINTAINER only; writes the truth source)

Effect:
- apply `GCPlan.json` actions to `tools/index/gc_state.json`.

V0 safety:
- may only modify the state file
- must not move/delete any `.lean`

Command:

```bash
uv run --locked python tools/gc/gc.py apply \
  --repo-root . \
  --plan .cache/leanatlas/gc/propose/GCPlan.json \
  --out-root .cache/leanatlas/gc/apply \
  --mode MAINTAINER
```

---

## Roots

### `roots.json`

Meaning:
- Seeds listed here are pinned and must not be collected (Nix gcroots style).

Format:

```json
{"version":"0.1","pinned_seeds":["LeanAtlas.Incubator.Seeds.Demo.SeedA"]}
```

### `gcroots/` (local symlink roots)

- gitignored by default.
- Use it to temporarily pin Seeds for debugging/experiments.

---

## Seeds state source of truth (must know)

- `tools/index/gc_state.json`
  - lifecycle state: `active / quarantined / archived`
  - schema: `docs/schemas/GCState.schema.json`
  - contract: `docs/contracts/GC_STATE_CONTRACT.md`

---

## Related contracts and reuse notes

Contracts:
- `docs/contracts/GC_GATE_CONTRACT.md`
- `docs/contracts/GC_STATE_CONTRACT.md`
- `docs/contracts/PROBLEM_STATE_CONTRACT.md`

Reuse:
- `docs/reuse/GC_REUSE.md`
