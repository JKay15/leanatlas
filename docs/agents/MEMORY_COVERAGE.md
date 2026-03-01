# Memory Coverage (Contrast: Project Memory Documentation v7 → Codex Documentation Package)

>Purpose: You are right - we must regularly check the "long-term memory document" to prevent the Codex document from missing key components.
> This article maps the key points of `LeanAtlas_Project_Memory_2026-02-22_v7.md` to the Codex documents/contracts/tests in the warehouse.

## 0.5) User’s hard requirements for “reply/document/project” (must be written into the system, not relying on memory)

These are not "style preferences", but engineering constraints that directly affect whether Codex can correctly implement and maintain LeanAtlas:

- **The meaning of each term must be explained**: Any field/file/process name must be defined for the first time (to avoid the recurrence of "the word pipeline cannot be understood").
- Correspondence: Required term definition at the top of all contracts/execplans; `REPORTING_CONTRACT`/`RUNREPORT_CONTRACT`/Phase3 ExecPlans.

- **TDD is not a slogan**: The key access control of each phase must have a runnable test matrix, and it must cover the real workflow (not just the test tool itself).
- Corresponding: `docs/contracts/TESTING_CONTRACT.md` + `tests/manifest.json` (test registry) + `docs/testing/TEST_MATRIX.md` (matrix)

- **E2E must be "sequential + stress testing + regression chain"**: it cannot only test a single question; it must be able to trigger the scenario of "fixing one to detonate more".
- Corresponding to: `docs/contracts/E2E_SCENARIO_CONTRACT.md` + `tests/e2e/scenarios/**`

- **Don’t reinvent the wheel**: For classic requirements such as deduplication/promotion/recycling, give priority to mature implementations or portable scripts from the mathlib/Lean community, and then encapsulate them into gates.
- Especially **identity/roots/reachability/grace period** these classic elements: priority alignment Lean’s module name rule, Nix’s gcroots model, Git’s pruneExpire grace period (replacing ‘time’ with the domain logical clock).
- Corresponding to: Phase3 Dedup/Promotion/GC ExecPlans clearly writes "which wheels are reused to solve which problems".

- **External dependencies must be pinned + installable + verifiable**: All external tools/libraries must have pinned versions, clear installation methods, and be verified with smoke tests.
- Corresponding: `THIRD_PARTY_DEPENDENCY_CONTRACT` + `tools/deps/pins.json` + `docs/setup/**` + `tests/setup/**`

- **Python dependencies must follow the uv standard**: use `pyproject.toml + uv.lock` (requirements.txt is not allowed).
- Corresponding to: repo root `pyproject.toml` + `uv.lock` + setup docs + contract tests.

- **Codex is the protagonist**: Codex is not just about writing Lean; it must participate in knowledge base/skill base/automation maintenance (especially Advisor automation).
- Corresponding: `docs/contracts/AUTOMATION_CONTRACT.md` + `automations/registry.json` + `docs/agents/AUTOMATIONS.md`

---

## 1) Covered (this warehouse has a clear contract + tests)

- **Dual mode (Operator/Maintainer)**:
- Root `AGENTS.md`
  - `docs/agents/OPERATOR_WORKFLOW.md`
  - `docs/agents/MAINTAINER_WORKFLOW.md`

- **Small loop product three-piece set + schema**:
  - `docs/contracts/REPORTING_CONTRACT.md`
  - `docs/contracts/RUNREPORT_CONTRACT.md`
  - `docs/contracts/RETRIEVAL_TRACE_CONTRACT.md`
  - `docs/schemas/*` + `tests/schema/*`

- **PatchScope and Judge deterministic**:
  - `tools/workflow/*`
  - `tests/contract/check_patch_scope_policy.py`
  - `tests/contract/check_judge_determinism.py`

- **E2E (case + scenario) specifications and verification**:
  - `docs/contracts/E2E_CONTRACT.md`
  - `docs/contracts/E2E_SCENARIO_CONTRACT.md`
  - `tests/e2e/validate_cases.py`
  - `tests/e2e/validate_scenarios.py`

- **Test Registry + Test Matrix (to prevent "tests are written but invisible to CI")**:
  - Registry:`tests/manifest.json`
  - Matrix:`docs/testing/TEST_MATRIX.md`
  - Gates:`tests/contract/check_test_registry.py` + `tests/contract/check_test_matrix_up_to_date.py`

- **AI-native/vibe-coding engineering disciplines (Codex must comply)**:
  - `docs/contracts/AI_NATIVE_ENGINEERING_CONTRACT.md`

## 2) Completion in this round (the two items you reminded: lean-lsp-mcp + Automations TDD + external dependency installation)

### 2.1 MCP:lean-lsp-mcp / MSC2020
- Contract (Phase1 level access document):
  - `docs/contracts/MCP_ADAPTER_CONTRACT.md`
  - `docs/contracts/MCP_LEAN_LSP_MCP_ADAPTER.md`
  - `docs/contracts/MCP_MSC2020_CONTRACT.md`

- Tool entrance (first stub the fixed interface, and then implement it later):
  - `tools/mcp/healthcheck.py`

- Installation and verification (to prevent Codex "Tool not found"):
  - `docs/setup/DEPENDENCIES.md`
  - `docs/setup/external/lean-lsp-mcp.md`
  - `docs/setup/external/ripgrep.md`
  - (tests)`tests/setup/deps_smoke.py`(nightly tier)

### 2.2 Automations: Specifications + TDD
- Single source of truth:
  - `automations/registry.json`
-Contract and instructions:
  - `docs/contracts/AUTOMATION_CONTRACT.md`
  - `docs/agents/AUTOMATIONS.md`
- TDD(core gate):
- `tests/automation/validate_registry.py` (specification verification)
- `tests/automation/run_dry_runs.py` (run dry-run on active/core automations)

> Conclusion: Automations are no longer a "macro slogan" but measurable components that go into the gate.

## 3) Partial coverage (with skeleton but still needs Phase3/4 landing)

- **Library Growth(Dedup/Promotion/GC)**:
- Already have: schemas + contracts (`docs/schemas/DedupReport.schema.json`, etc.)
- Finalized: DedupGate V0 gives priority to reusing the canonicalization idea of ​​the mathlib community's duplicate-declaration linter (binder dependency awareness + alias filtering)
- Still missing: algorithm implementation and sequence scenario of real DedupGate/Promotion/GC

- **Domain-driven retrieval (MSC integrated into retrieval pruning)**:
- Already: General structure of Retrieval ladder
- Still missing: deterministic implementation and tests of MSC→domain bundle→imports routing

## 4) Still not covered ("mature wheels" list from memory document, must be included in subsequent ExecPlan)

These are clearly stated in the memory document as "don't reinvent the wheel", but the current Codex documentation package has not written them into contracts/tools/tests:

- Import graph analysis (for imports management and module reconstruction access control)
- It has been specified in the GC reuse list: `docs/reuse/GC_REUSE.md` (but it still needs to be further implemented in Promotion/Imports management + tests)
- mathlib linters (directoryDependency/minImports etc.)
- "ontology MCP" reference implementation (can learn from interface shape and version strategy)

> Processing strategy: Write "which wheels to reuse" as hard entries in the ExecPlan of Phase3/4, and add TDD (at least smoke + contract) to them.

## 5) Next control point (to prevent further leakage)

Every time you extend a Codex documentation package, you must check:

- MCP: Is there a clear degradation path + healthcheck + AttemptLog observation field
- Automations: whether there are registry entries + dry-run + core/nightly tier classification
- External dependencies: whether to clear installation and verification + whether there is a smoke test
- Reuse wheels: Whether to specify "which wheel to use to solve which problem" in ExecPlan
