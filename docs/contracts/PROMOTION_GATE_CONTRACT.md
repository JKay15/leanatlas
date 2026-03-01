# PROMOTION_GATE_CONTRACT v0.3

This contract defines the **public interface** of LeanAtlas PromotionGate (inputs/outputs/evidence/gates) and hardens “advanced practice” into executable obligations:

- reuse evidence (Rule-of-Three default)
- compat migration (mathlib-aligned)
- import-structure audits
- domain boundary audits

Goal: Codex can reliably produce a **promotion proposal + rollbackable patch**, but whether the promotion is allowed is decided by deterministic gates (Lean env + rules).

---

## 0) V0 scope (do the 4 most important things)

PromotionGate V0 must cover:

1) **Reuse evidence (Rule-of-Three default)**
   - Default: before entering Toolbox, a candidate tool must be used in **≥3 distinct problems** (`problem_slug` count).
   - Exceptions are allowed, but must be explicit and justified (e.g. major friction reduction, canonical domain variant).

2) **Compat migration (mathlib-aligned)**
   - Declaration rename: prefer a deprecated alias (`deprecate to` / `@[deprecated] alias old := new`).
   - Module rename/split: keep old modules as compat stubs and use `deprecated.module` linter so downstream migrates instead of exploding.

3) **Import-structure audits (mathlib toolchain)**
   - Required audit signals:
     - `#min_imports in ...` output
     - import-graph edges (if available)
     - `upstreamableDecl` linter warnings
     - `directoryDependency` linter warnings

4) **Rollbackable + auditable output**
   - Must produce: `PromotionReport.json` (machine) + `PromotionReport.md` (human).
   - Any promotion must be applied as a patch/PR (no silent mutation).

V0 may start with WARN-heavy structural gates (collect data first), but it **may not downgrade**:
- do not substitute regex/text heuristics for Lean/mathlib tool outputs.
- if a required tool fails to run, the corresponding gate must be `passed=false` and must attach stdout/stderr evidence.

---

## 1) Terms

- **Seed**: candidate tools under `LeanAtlas/Incubator/Seeds/**`.
- **Toolbox**: official reusable tools under `LeanAtlas/Toolbox/**`.
- **Promotion**: move a set of declarations/modules from Seeds into Toolbox and provide compat migration.
- **Evidence (reuse evidence)**: real usage records traceable to artifacts (AttemptLog/RunReport) across specific problems and run_ids.
- **Rule-of-Three**: default policy: used in ≥3 distinct `problem_slug`s.
- **Compat layer**: deprecated aliases / deprecated module stubs / re-exports to avoid downstream breakage.
- **Bad duplicate**: same statement/semantics duplicated (should be alias/deprecation, not a second proof).
- **Good duplicate (variant)**: a standard variant with a different statement/interface, explicitly marked and justified.
- **Gate**: auditable check entry: `gate`, `passed`, `evidence` (evidence must not be empty).
- **Advisor (Codex)**: may propose plan/patch/migrations, but cannot override gate decisions.

---

## 2) Input: PromotionPlan

File: `PromotionPlan.json`
Schema: `docs/schemas/PromotionPlan.schema.json`

V0 must remain extensible: avoid hard enums that lock future upgrades.

### 2.1 Required top-level fields

- `version: string`
  - PromotionPlan format version.

- `meta: object`
  - provenance + reproducibility metadata (recommended):
    - `generated_at` (ISO8601)
    - `mode` (`MAINTAINER` or `OPERATOR`)
    - `source` (`automation:<id>` / `manual` / `codex`)
    - `git` (commit/branch/dirty)
    - `toolchain` (Lean/Lake/mathlib summary)

- `policy: object`
  - thresholds and switches; must be explicit per plan.
  - recommended V0 fields:
    - `min_reuse_problems: int` (default 3)
      - counted by **distinct `problem_slug`** (no double-counting attempts within one problem).
    - `scope_prefixes: string[]` (default `["LeanAtlas"]`)
    - `allow_exceptions: bool` (default true)
    - `allow_force_deposit: bool` (default true)
      - allows explicit human-requested deposition for selected tools when accompanied by justification.

- `candidates: array`
  - candidate list.

### 2.2 candidates[i] required fields

- `source: string`
  - where the candidate comes from (Seed dir/module identifier).

- `decls: array`
  - declarations to be promoted.

Each `decls[j]` must include:
- `name: string` (Lean declaration name)

### 2.3 Recommended fields (where “good vs bad duplicates” becomes real)

- `intent: object`
  - recommended keys:
    - `kind: string` (suggested values: `canonical|variant|alias|compat` — not locked)
    - `variant_of?: string` (canonical decl name if this is a variant)
    - `justification?: string` (why the variant/exception is legitimate)
  - rules:
    - same-statement renames must be alias/deprecation, not duplicated proofs.

- `domain: object`
  - MSC/local domain id for routing and grouping.

- `evidence: object`
  - traceable refs to artifacts, recommended:
    - `uses_value_runs: string[]`
    - `problems: string[]` (used to count distinct `problem_slug`)
    - `attempt_refs: string[]` (paths with optional line anchors)

- `target: object`
  - desired Toolbox location (module/path). May be empty in V0, but final placement must be recorded in the PromotionReport.

- `migration: object`
  - compat/rollback strategy (alias/deprecated module/reexport), recommended:
    - `strategy: string`
    - `since?: string` (YYYY-MM-DD)
    - `notes?: string`

---

## 3) Output: PromotionReport

Files: `PromotionReport.json` + `PromotionReport.md`
Schema: `docs/schemas/PromotionReport.schema.json`

### 3.1 Required top-level fields
- `version`
- `promotion_targets`
- `gates[]` (each must include `gate/passed/evidence`, evidence non-empty)
- `decision` (`passed/reason_code/notes?`)
- `summary`

### 3.2 Required V0 gate names (must all appear)
V0 may treat some as WARN (by policy), but entries must exist and must include evidence.

Hard gates (fail ⇒ reject promotion):
1) `mode_and_scope_check`
2) `build_snapshot_ok`
3) `candidate_existence_and_type_ok`
4) `dedup_gate_present_and_ok`
   - evidence must include `dedup_report_path` + `dedup_report_hash`
5) `reuse_evidence_policy_ok`
   - default: distinct problems < `policy.min_reuse_problems` ⇒ FAIL
   - exception: if `policy.allow_exceptions=true`, may downgrade to WARN only if `intent.justification` is non-empty and evidence explains friction reduction/standard variant
   - force-deposit: if `intent.force_deposit=true` or tool name is listed in `tools/index/force_deposit.json`, gate may pass only when `intent.justification` is non-empty and `policy.allow_force_deposit=true`
6) `migration_and_rollback_plan_present`
7) `verification_ok` (must run `lake test` and `lake lint`)
8) `dependency_pins_ok` (see THIRD_PARTY_DEPENDENCY_CONTRACT)

Structural signals (V0 default WARN, but must produce raw evidence):
9) `import_minimization_audit`
   - evidence must include raw tool output, reproducible cmd, and sha256
10) `directory_boundary_audit`
   - evidence must include raw output + cmd + sha256; tool failure must not be skipped
11) `upstreamable_decl_audit`
   - evidence must include raw output + cmd + sha256; tool failure must not be skipped
12) `compat_deprecation_audit`
   - evidence should include file locations of alias/stubs and `since` date if applicable

---

## 4) “Good vs bad duplicates” and DedupGate

- DedupGate V0 hard-fails only **instance hard duplicates**; these are almost always bad duplicates.
- PromotionGate’s “good duplicates” are **variants** (different statement/interface), not duplicate proofs of the same statement.
- Same-statement rename must be handled by alias/deprecation.

---

## 5) TDD test matrix (must reflect real workflow)

### 5.1 Core profile (every PR)
- schema fixtures for PromotionPlan/PromotionReport (positive + negative)
- contract smoke: PromotionReport must include all required gate names
- dependency governance: pins/lock/docs consistency

### 5.2 Nightly profile (real workflow: Lean build/test/lint)
- Rule-of-Three pass/fail
- exception pass must be WARN + justification
- reject bad duplicate (duplicate proof of same statement)
- accept variant with `variant_of`
- migration: declaration rename uses deprecated alias; module move keeps compat stub and produces `deprecated.module` warning

### 5.3 Soak profile (extreme sequence)
- 50+ promotions (fixture overlay) with interleaved rollbacks and re-promotions
  - must not accumulate garbage
  - clean/clobber must restore a clean workspace
  - downstream imports must remain valid due to compat layer

---

## 6) Tools and sources (advanced practice, no wheel reinvent)

PromotionGate relies on mature mathlib tooling:
- `#min_imports in`
- linters: `directoryDependency`, `upstreamableDecl`, `deprecated.module`
- `deprecate to` / `DeprecateTo`
- `#clear_deprecations` (enables future remove-deprecations automation)

If any additional external tool is introduced, it must follow:
- `docs/contracts/THIRD_PARTY_DEPENDENCY_CONTRACT.md` (pins + install docs + smoke)
