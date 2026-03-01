# ExecPlan: Phase3 — DedupGate V0 (instances, hard gate)

Purpose: turn “duplicate instances” into a **testable, auditable, automatable** closed loop.
This plan does exactly one thing: **DedupGate V0 (instances only)**.

## 0) Background and goals

### Background
In Lean projects, duplicate declarations / duplicate instances can cause:
- library bloat (higher retrieval/maintenance cost)
- wheel reinventing (existing tools get shadowed)
- harder migrations (multiple versions survive refactors)

### V0 goal (narrow, high ROI)
- scan only: **typeclass instances**
- detect only: **hard duplicates** (same canonicalized type key; in particular, duplicates caused by binder reordering)
- output: `DedupReport.json` + `DedupReport.md` (must validate against schema)
- gate: actionable duplicates > 0 ⇒ FAIL (Promotion must consume this report)

## 1) Glossary (every term must be executable)
- **Env / Environment**: the set of declarations after compilation (the only authority).
- **Declaration**: a constant in the env (def/theorem/axiom/instance, …).
- **Instance**: a declaration with the `[instance]` attribute (must be detected via Lean APIs, not by name heuristics).
- **Hard duplicate**: two instances whose **canonical type key** is identical and not allowlisted/aliased.
- **Canonical key**: a normalized, hashable representation of the instance type.
- **Allowlist**: explicit exceptions where multiple instances are intentionally kept (rare; must include a reason).
- **Alias**: a declaration whose value is just a thin wrapper calling another constant (compat/rename); should not be treated as a duplicate implementation.

### 1.1 Bad duplicates vs good duplicates (align with PromotionGate)
- DedupGate V0 hard-gates only **typeclass instance hard duplicates** (same canonical key).
  - these are almost always **bad duplicates**: they destabilize typeclass search and pollute retrieval/maintenance.
- “Good duplicates” in PromotionGate are standard variants (different statements / interfaces) and typically do not share the same canonical key.
- “Same statement, different name” is not a good duplicate: it should be handled as alias/deprecation.
- Rare cases where multiple instances must exist: require an **Allowlist** entry with reason and scope, and Promotion must cite it in PromotionReport.

## 2) Reuse a mature wheel: adopt mathlib-style canonicalization

### 2.1 Why we do not reinvent this
We do not re-invent binder permutation/canonicalization from scratch.
Community practice exists: scan env → telescope → dependency-aware binder normalization → de Bruijn abstraction → stable key.

V0 adopts this engineering direction by reusing a mathlib-style duplicate-declaration canonicalization approach (dependency-aware ordering + deterministic tie-break + alias filtering).
This satisfies the earlier “binder swap normalization” requirement without creating a new bespoke system.

### 2.2 Canonical key definition (frozen for V0)
Given an instance `c : τ`:

1) take `τ` and instantiate type-level params
2) telescope-expand:
   - binders `x₁ … xₙ` (each has BinderInfo + type)
   - body `e`
3) dependency-aware reorder of binders:
   - at each step, compute the set of candidate binders whose types do not depend on any remaining binder
   - deterministically sort candidates (stable expression order / stable tie-break)
   - choose the smallest binder, move it to the canonical order
   - abstract it into a de Bruijn variable, and update remaining binder types + body accordingly
   - repeat
4) final key is the concatenation of:
   - canonical binder sequence `(BinderInfo, normalized binderType)`
   - normalized body `e`
5) serialize to stable bytes/string and hash as `type_hash`

Important:
- the key must be fully deterministic and independent of pretty-printing
- do not use `toString` directly as the key

## 3) Scan scope and noise filters

### 3.1 Scope
V0 scans only:
- instances under the `LeanAtlas.*` namespace (Toolbox/Seeds/Compat/Kernel, …)

Rationale:
- we only hard-gate duplicates introduced by this project
- mathlib/core may contain historical duplicates; V0 should not be blocked by external noise

V1/V2 may add warnings about collisions with mathlib/core (not hard fail unless Promotion).

### 3.2 Noise filters
- skip internal/implementation detail names
- skip deprecated declarations (unless explicitly checking migration)
- skip aliases (see next section)

## 4) Alias and Allowlist

### 4.1 Alias detection (mandatory)
If a declaration `c`’s value (after unfolding/eta normalization) is a direct call to another constant `d` (e.g. `Expr.const d _` up to equivalence), then:
- this is compat/rename, not a duplicate implementation
- DedupGate must not block it (but may record it as `alias` in the report)

This supports Promotion/refactors with deprecated aliases.

### 4.2 Allowlist (explicit exceptions)
File:
- `tools/dedup/allowlist.json`

Each entry must include at least:
- `type_hash` (or duplicate-group key)
- `names` (allowed declaration names)
- `reason` (why allowed)
- optional `expires_after` (prevent permanent junk)

Allowlist is an exception, not an escape hatch:
- allowlist changes require review
- DedupReport must reflect allowlist hits

## 5) Output: DedupReport (machine + human)

### 5.1 JSON (machine)
Suggested path:
- `artifacts/dedup/DedupReport_<ts>.json`
Schema:
- `docs/schemas/DedupReport.schema.json`

Each candidate should include at least:
- `candidate.name`
- `candidate.module` (if available)
- `candidate.type_hash`
- `decision` (string; extensible)
- `evidence` (why duplicate: same key / alias / allowlist hit, …)
- `related` (other declarations in the group)

### 5.2 Markdown (human)
Suggested path:
- `artifacts/dedup/DedupReport_<ts>.md`

Include:
- summary: number of groups, actionable count
- per-group: key summary, decls, module locations, recommended action

## 6) Gate integration (closed loop)

### 6.1 Promotion must consume DedupReport
Before Promotion:
- run DedupScan
- actionable duplicates > 0 ⇒ Promotion FAIL
- if all duplicates are allowlisted/aliases ⇒ Promotion may continue

### 6.2 CI gate
If a PR triggers Promotion or modifies Toolbox/Seeds, CI must run DedupScan and read DedupReport.

## 7) TDD (sequence + extremes from day one)

### 7.1 Unit tests (Lean)
Goal: canonicalization is deterministic.
- `key_perm_001`: swap independent binders ⇒ same `type_hash`
- `key_dep_001`: dependent binder case ⇒ illegal swaps must not collapse keys

### 7.2 E2E tests
- `dup_inst_001`: inject two instances with same key ⇒ DedupReport actionable>0 ⇒ gate FAIL
- `dup_inst_allow_001`: same duplicate but allowlisted ⇒ gate PASS and report must cite allowlist

### 7.3 Scenario (sequence)
- `seq_dedup_inst_001`:
  1) introduce duplicate ⇒ FAIL
  2) fix (delete/merge/alias) ⇒ PASS
  3) later change introduces new duplicate ⇒ FAIL

Goal: catch “fixed then regressed” chains.

## 8) Automation (unattended advisor)
Registry entry:
- `automations/registry.json` → `nightly_dedup_instances`

Rules:
- deterministic step: scan only, produce DedupReport
- advisor step: only if actionable duplicates exist; generate a fix PR (remove duplicates / merge / add deprecated alias)
- verify: `lake build` + `lake test`

DedupScan itself is deterministic; Codex only helps with patch generation.

## 9) Implementation checklist (minimal actionable list)
- [ ] implement DedupScan (MetaM over env)
- [ ] provide `lake exe leanatlas_dedup_scan` with args: `--instances --out <path> --scope LeanAtlas`
- [ ] implement allowlist (`tools/dedup/allowlist.json`)
- [ ] emit DedupReport (json+md) and validate schema
- [ ] add tests: unit + e2e + scenario skeleton
- [ ] update automation registry: planned → active after scan runs in nightly
