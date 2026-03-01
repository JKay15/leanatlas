# Decision Log (Single Source of Truth)

- D-0001: All external dependencies must be pinned, documented, and smoke-verified; Python dependencies follow uv (`pyproject.toml + uv.lock`).
  - Date: 2026-02-23
  - Impact: `docs/setup/**`, `tools/deps/pins.json`, `pyproject.toml`, `uv.lock`, contract tests
  - Why: Prevent version drift from breaking workflows; keep runs reproducible
  - Evidence: `docs/contracts/THIRD_PARTY_DEPENDENCY_CONTRACT.md`

- D-0002: Stable Seed identity (`seed_id`) uses Lean module names, not file paths.
  - Date: 2026-02-23
  - Impact: GC/Promotion/Dedup reports and indexes; import-graph integration
  - Why: Lean import/environment/tooling uses module name as primary key
  - Evidence: `docs/contracts/GC_STATE_CONTRACT.md`

- D-0003: GCGate V0 does not move/rename Seed `.lean` files; it only updates `gc_state.json` (metadata isolation).
  - Date: 2026-02-23
  - Impact: `tools/gc/**`, `tools/index/gc_state.json`, GC tests/scenarios
  - Why: moving files changes module paths and can break imports; V0 prioritizes stable loop closure
  - Evidence: `docs/contracts/GC_GATE_CONTRACT.md`

- D-0004: GC roots must be selected by domain-layer active problems; `Problems/*/State.json` is the state source of truth.
  - Date: 2026-02-23
  - Impact: `Problems/*/State.json`, `tools/problem_state/reconcile.py`, `tools/gc/**`
  - Why: manage Seeds by real domain progress and avoid noisy oscillation; state machine avoids path-guessing
  - Evidence: `docs/contracts/PROBLEM_STATE_CONTRACT.md`

- D-0005: Revival policy: quarantined -> active on one real reuse hit; archived -> two-phase restore (second independent hit inside pending window for full revival).
  - Date: 2026-02-23
  - Impact: `tools/gc/**`, `tools/index/gc_state.json`, GCPlan/Report schema
  - Why: avoid global pollution from accidental one-off hits while keeping an auditable recovery path
  - Evidence: `docs/contracts/GC_GATE_CONTRACT.md`

- D-0006: Promotion defaults to Rule-of-Three (reuse in >=3 distinct problems) for Toolbox admission; structured exceptions are allowed.
  - Date: 2026-02-23
  - Impact: PromotionPlan/Report, PromotionGate tests/scenarios
  - Why: industrial/library experience says abstraction must be earned, with explicit high-value exceptions
  - Evidence: `docs/contracts/PROMOTION_GATE_CONTRACT.md`

- D-0007: PromotionGate structural signals must come from real Lean/mathlib toolchain evidence; heuristic degradation/skip is forbidden.
  - Date: 2026-02-23
  - Impact: `tools/promote/**`, `docs/contracts/PROMOTION_GATE_CONTRACT.md`, Phase3 scenarios/tests
  - Why: structural signals are useful only when reproducible and auditable
  - Evidence: `docs/contracts/PROMOTION_GATE_CONTRACT.md` (v0.3)

- D-0008: Phase6 introduces real agent evaluation and skills-growth gating.
  - Date: 2026-02-24
  - Impact: `docs/contracts/AGENT_EVAL_CONTRACT.md`, `docs/contracts/SKILLS_GROWTH_CONTRACT.md`, Phase6 task/scenario pipelines
  - Why: evaluate real workflows, not toy tests; ensure skill growth is evidence-backed
  - Evidence:
    - `docs/contracts/AGENT_EVAL_CONTRACT.md`
    - `docs/contracts/SKILLS_GROWTH_CONTRACT.md`

Notes:
- Oracle packs for agent eval are external by default (not committed in repo) to avoid answer leakage.
- The repo stores task definitions and publicly auditable expectations only.
