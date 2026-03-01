# MAINTAINER workflow (build/evolution period, for Codex execution)

> Goal: When you need to modify the system (Toolbox/Incubator/tools/contracts/tests/skills), make the behavior of Codex controllable, auditable, rollable, and testable.
> The repository is in OPERATOR mode by default; MAINTAINER must be explicitly enabled by a human (local `AGENTS.override.md`, gitignored).

The maintenance period also follows AI-native engineering disciplines (no "no verification vibe coding"):
- `docs/contracts/AI_NATIVE_ENGINEERING_CONTRACT.md`

---

## When must I enter MAINTAINER?

As long as any of the following situations occur, MAINTAINER is **required** (OPERATOR does not allow hard modification):

- Need to modify `LeanAtlas/**` (Toolbox/Incubator/Kernel/Compat)
- Need to modify `tools/**`
- Need to modify `docs/contracts/**` or `docs/schemas/**`
- Need to modify `tests/**` (including new e2e/scenario/soak)
- Need to modify `.agents/**` (skills, agent configuration)
- Requires bump toolchain / mathlib version (`lean-toolchain` / `lakefile.lean`)

---

## Prerequisites for MAINTAINER (don’t guess)

### External dependencies (installation and verification)

MAINTAINER will use more external wheels/tools; don't let Codex "fly by feel".

- Dependency list: `docs/setup/DEPENDENCIES.md`
- Depends on pin source of truth: `tools/deps/pins.json` (any external wheel must be pinned version here)
- Python pins: `pyproject.toml` + `uv.lock` (uv standard: declaration + lockfile; required for core tests)
- MCP (lean-lsp-mcp) installation: `docs/setup/external/lean-lsp-mcp.md`
- Depends on smoke (nightly): `python tests/run.py --profile nightly`

> Constraints: Any PR for "adding/upgrading external dependencies" must also add/update:
> - `tools/deps/pins.json` (machine-readable pin)
> - If Python is involved: After updating `pyproject.toml` you must run `uv lock` and submit the updated `uv.lock` (lockfile is considered a pin)
> - Installation/verification documentation page (`docs/setup/external/<name>.md`)
> - at least one smoke verification (nightly tier)
>
> And disallowed: `@main` / `latest` / unpinned `git+https`.

- **local** `AGENTS.override.md` exists in the repository root and the file should not be committed (it is ignored in `.gitignore`).
- You must read first:
- `docs/agents/STATUS.md` (current stage and next step)
- `docs/agents/PLANS.md` (ExecPlan specification)
- `docs/contracts/DETERMINISM_CONTRACT.md` (deterministic requirement)
- `docs/contracts/THIRD_PARTY_DEPENDENCY_CONTRACT.md` (external dependencies/supply chain: pins, audits, rollbacks)
- `docs/contracts/WORKFLOW_CONTRACT.md` (workflow contract)

---

## Core disciplines (must be observed)

### 1) Non-trivial changes must be written in ExecPlan first
- ExecPlan file path: `docs/agents/execplans/<YYYYMMDD>_<short_name>.md`
- The plan must be self-contained (others can reproduce it without watching the chat)
- The plan must include: test strategy (TDD), rollback strategy, acceptance criteria, risks

### 2) Test first and then change (TDD)

> **Automations must also be TDD**:
> - When modifying `automations/registry.json` or any automation entry script, you must first make `tests/automation/*` red and then change it to green.
> - Any automation with `status=active` must provide `tdd.dry_run` and enter `tests/run.py --profile core` or `--profile nightly`.
> See: `docs/contracts/AUTOMATION_CONTRACT.md` and `docs/agents/AUTOMATIONS.md` for details.

- Any bugfix/contract change/runner change: first patch or adjust the test to make it red, then make it green.
- Minimum requirement: `python tests/run.py --profile core` must pass.
- Involves executing e2e: running at least one scenario (see below).

### 3) Do not pollute the real library
- Temporary Toolbox/Seeds content for testing can only be injected via **workspace overlay** (`.cache/leanatlas/**`).
- Writing and submitting test-only content to `LeanAtlas/Toolbox/**` is not allowed.
- After the changes are completed: `git status --porcelain` must be empty (the tracked file must not have any remaining changes).

### 4) Any changes that “change the shape of the interface” must update the contract and schema simultaneously
- If you modify the RunReport/RetrievalTrace/AttemptLog shape:
- Update `docs/contracts/*`
- Update `docs/schemas/*`
- Update `docs/examples/*`
- Update schema fixtures (`tests/schema/fixtures/**`)

---

## Recommended command entry (local)

> These commands are the entrance to "real usage scenarios" and should be used first.

- Build (compile Lean code):
  - `lake build`

- Run tests (workflow tests):
- `lake test` (equivalent to `python tests/run.py --profile core`, and extensible)
- Execution type e2e (requires Lean + mathlib):
    - `python tests/e2e/run_cases.py --profile core`
    - `python tests/e2e/run_scenarios.py --profile core`

- Run lint (discipline check):
- `lake lint` (currently bound to deterministic core gate, can be tightened later)

---

## Common maintenance tasks runbook (placeholder skeleton, will be refined one by one in the future)

> These are the "main maintenance actions" for subsequent phases of LeanAtlas. Now fix the entrance and acceptance form to avoid future drift.

### A) Modify Promotion/Dedup/GC (Library Growth System)
1. Write ExecPlan (define gate, dedup criterion, rollback point)
2. Add/update tests:
   - contract/unit(deterministic)
- e2e scenario (sequential regression)
3. Implement tool scripts (`tools/**`)
4. Output sample report (md+json of DedupReport/PromotionReport/GCReport)
5. Acceptance: core + at least 1 scenario + repo clean

### B) Skills regeneration (Agent Adaptation System)
1. Write ExecPlan: input (Toolbox/telemetry) → output (_generated/** + skills)
2. The generator must be runnable without LLM (deterministic)
3. The generated results must be auditable (readable by PR diff) and rollable
4. Acceptance: schema/contract passes + skills can be loaded by Codex

### C) Domain/MSC MCP (ontology dictionary service)
1. Write ExecPlan: schema, version strategy, interface compatibility strategy
2. Add protocol-level tests (input query → output top-k / path)
3. Add integration tests (MCP is optional: if it exists, it will be called; if it does not exist, it will be stub)
4. Acceptance: Can be run locally + does not affect OPERATOR default workflow

### D) Toolchain/mathlib bump
1. Write ExecPlan: target version, rollback method, CI impact
2. Update:
   - `lean-toolchain`
- mathlib tag for `lakefile.lean`
3. Run: `lake update` → `lake build` → `lake test`
4. Update: any contracts/tests breakage caused by version changes

---

## Maintenance output (must be written into PR / Delivery Notes)

Each maintenance change should provide at least:
- Summary of changes (why the change was made)
- Affected interfaces (contracts/schemas/skills/tools)
- Add/update test list (how to verify)
- Rollback strategy (how to return to the previous stable state)


### E) Automations (background tasks)
1. Write ExecPlan: describe trigger conditions, deterministic steps, Advisor output, verification, and rollback.
2. Update `automations/registry.json` (single source of truth).
3. Complete tests first:
- `tests/automation/validate_registry.py` (spec level)
- For active automation: add `tdd.dry_run` and include it in core/nightly
4. Implement/update the entry script (`tools/**`).
5. Acceptance: `lake test` + (if necessary) nightly tier.
