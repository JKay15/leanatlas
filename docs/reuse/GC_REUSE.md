# GC (collection loop) — reusable wheels (V0)

This file answers a practical question:
**For “Seeds/Toolbox retirement/cleanup”, what mature implementations can we reuse?**

Reality (not pessimism):
- In the Lean ecosystem, a one-click “delete unused theorems automatically” tool is not a widely adopted standard.
- But we can reuse three families of proven ideas:
  1) Classic GC: **roots / reachability / two-stage deletion** (industrial instances: Nix, Git).
  2) mathlib’s **deprecation → migration → cleanup** ecosystem (the canonical route for “Toolbox GC”).
  3) mathlib/leanprover-community’s **import-graph** + Lake’s **clean/cache/shake** (mature for dependency graphs and hygiene).

LeanAtlas V0 strategy:
- Seeds GC = **convergence + noise reduction** (quarantine/archive), default **no physical deletion**.
- Toolbox “GC” = **deprecation lifecycle** (compat first, migrate, then delete).

---

## 1) import-graph (strongly recommended reuse)

### What we reuse
- `lake exe graph` generates module import graphs (JSON/HTML/PDF outputs, etc.).
- import analysis utilities (redundant imports, minimal imports, upstream placement hints).
- key capability: **source-file-based import analysis** (parse imports from source files).

### Why it fits LeanAtlas GC
- Seeds GC needs a `SeedModule → SeedModule` import edge list.
- Writing our own parser is possible, but it risks:
  - edge syntax cases
  - future grammar drift
  - mismatches with Lean’s real import behavior
- import-graph is long-used by the community → classic “don’t reinvent wheels”.

### V0 integration
- GCGate import-edges stage:
  - prefer import-graph
  - if unavailable, downgrade to conservative text scanning (`import` lines only)
- tests must include at least one fixture comparing our edge list against import-graph output (prevents silent drift).

### Version governance (important)
- import-graph tags often track Lean versions (e.g. `v4.28.0`).
- LeanAtlas governance:
  - forbid `@main/@master`
  - pin tag/commit in `tools/deps/pins.json`

### Local verification (no graphviz required)

```bash
lake exe graph --help
```

---

## 1.5) Lake: clean / cache clean / shake (built-in hygiene wheels)

These are not a full Seeds GC replacement, but they are mature cleanup capabilities already in the official toolchain:

- `lake clean`: delete build outputs (reset compile artifacts; useful for stress/repro/cleanup).
- `lake cache clean`: delete configured Lake artifact cache dir (controls cache bloat in CI/soak).
- `lake shake`: analyze which imports are truly needed; detect unused imports.

LeanAtlas reuse (V0):
- soak/stress cleanup: use `lake clean` (and optionally `lake cache clean`) to reset quickly.
- optional semantic signal: in nightly/soak GCGate.apply verification, run `lake shake` and record results into GCReport.

Caution:
- treat `lake shake` as an **advisor signal**, not the only truth.
- meta-programming/macros can produce edge cases; V0 requires **record/audit**, not auto-pruning.

---

## 2) Nix: GC roots pattern (reuse the idea, not a hard dependency)

### What we reuse
- “Roots expressed as a symlink set”:
  - to keep an object forever: add a root
  - to unpin: remove the root

### Why it fits LeanAtlas
- Seeds GC needs a “I know it’s cold, but do not touch it” pin mechanism.
- explicit roots are easier to audit than scattered comments.

### V0 integration
- `tools/gc/roots.json` as version-controlled truth.
- optional local overlay: `tools/gc/gcroots/` contains symlinks (gitignored).
  - effective roots = `roots.json ∪ gcroots/`.

---

## 3) Git: two-stage cleanup + grace period (reuse the idea)

### What we reuse
- Git’s `gc/prune` logic: do not delete immediately after something becomes unreachable; concurrency/misclassification is painful.
- Git uses `pruneExpire` (grace period) to reduce risk.

### Why it fits LeanAtlas
- Seeds GC can be “jittery”: just quarantined, then used again next task.
- LeanAtlas does not use wall-clock time; it uses a **domain logical clock**:
  - grace period = “after the same domain advanced by N problems”.

### V0 integration
- record thresholds explicitly in `GCPlan.policy` (`default_threshold`, `domain_thresholds`, `grace`).
- report must state exactly: which threshold/grace caused quarantine.

---

## 4) mathlib: deprecations + cleanup (the canonical Toolbox route)

### What we reuse
- mathlib already has mature deprecation/migration/cleanup tooling (including automation to remove old deprecated declarations).

### Why it fits LeanAtlas
- Toolbox is an API once external problems depend on it.
- deleting directly will break downstream.
- correct lifecycle: deprecate + compat + migrate + later delete.

### V0 integration
- Seeds GC does not touch Toolbox.
- Toolbox retirement goes through the deprecation contract, not Seeds GC.

---

## 5) LeanDojo (optional: high-fidelity usage edges)

LeanDojo can trace a Lean repo and produce higher-fidelity dependency evidence (premise-level usage).
Potential value for LeanAtlas GC:

- current usage edges in LeanAtlas mostly rely on `AttemptLog.uses_value` (lightweight).
- LeanDojo provides premise-level evidence that can improve:
  - true `Seed → Seed` dependencies (beyond “import exists”)
  - accurate counts of how many proofs truly used a Seed (helps Promotion and GC)

Practical constraints (why V0 does not hard-depend):
- tracing cost is high; best as nightly/offline eval.
- V0 first closes the loop with AttemptLog + import-graph (optional shake). Then add LeanDojo if needed.
