# LeanAtlas current stage status (single source of truth)

>Purpose: To prevent discussion drift and “the next step is forgotten”. This document should be updated as the phases progress.
> Read by Codex and maintainers by default: short, executable, and verifiable.

## Where are we now (as of 2026-03-08)

### LOOP mainline completion (project-level update, 2026-03-08)
- The remaining LOOP master-plan surfaces are now implemented on the current mainline.
- Newly completed mainline surfaces:
  - parent batch supervisor/autopilot
  - capability publication + bounded human-ingress + context rematerialization
  - default staged review execution backed by stored LOOP preferences
  - LeanAtlas worktree orchestration as a host adapter
  - reusable in-repo `looplib` packaging/docs/examples plus generic LOOP skills
- Canonical entry remains: `docs/agents/LOOP_MAINLINE.md`
- Standalone/non-LeanAtlas entry now also exists: `docs/setup/LOOP_LIBRARY_QUICKSTART.md`

### LOOP mainline (project-level update, 2026-03-07)
- LOOP is now a committed mainline system in LeanAtlas rather than a `.cache`-only experiment.
- Canonical entry: `docs/agents/LOOP_MAINLINE.md`
- That page is the authoritative matrix for:
  - implemented vs partial vs planned LOOP capabilities
  - `LOOP core` vs `LeanAtlas adapters`
  - how `.cache/leanatlas/tmp/**` experimental assets relate to mainline
- Project-level workflow/status docs must now stay aligned with that page.

### Phase 1 (completed and frozen): Reporting + Schemas + Determinism
- Schema and contract constraints of `RunReport.json / RetrievalTrace.json / AttemptLog.jsonl` have been frozen
- Established core gate: schema fixtures, referential integrity (refs), directory layout, canonical JSON, AGENTS size
- Goal: Make "Report Product Shape" a stable interface for all subsequent tools/visualizations/evaluations

### Phase 2 (has entered the executable state): Small loop workflow + Judge/Advisor + Budgets + E2E
- Small loop:Snapshot → Retrieval ladder → Attempt → Decide
- Decide layering: Advisor (optional, record) / Judge (deterministic referee, must be measurable)
- Budgets/stagnation has deterministic criteria
- E2E: golden cases + scenarios (sequence) + soak (pressure/soak)
- Key discipline: Test products only fall in `.cache/leanatlas/**` and `artifacts/**` (gitignore), and must not pollute `LeanAtlas/Toolbox/**`

### Codex document system (main skeleton has been implemented)
- OPERATOR:`docs/agents/OPERATOR_WORKFLOW.md`
- MAINTAINER:`docs/agents/MAINTAINER_WORKFLOW.md`
- LOOP mainline entry: `docs/agents/LOOP_MAINLINE.md`
- Lake standard entry: `lake test` / `lake lint` bound to workflow tests
- Automations: specifications + TDD into core gate (registry + contracts + tests)
- MCP: access contract skeleton (`docs/contracts/MCP_*`) + healthcheck stub (`tools/mcp/healthcheck.py`)
- External dependencies: unified pin + installation documentation + smoke (`docs/contracts/THIRD_PARTY_DEPENDENCY_CONTRACT.md`)

### Phase 3 (in progress): Library Growth System minimum closed loop (Dedup / Promotion / GC)
- Already have: JSON Schema + fixtures for `DedupReport / PromotionReport / GCReport`
- Already have: JSON Schema + fixtures for `PromotionPlan` (promotion proposal input)
- DedupGate V0 current implementation: source-backed instance scan via `tools/dedup/dedup.py`.
- Compiled-environment DedupGate scanning remains follow-on work.
- PromotionGate V0: Feed back "advanced experience" - Rule-of-Three default strategy, deprecated alias/module compat, min_imports / directoryDependency / upstreamableDecl structure signal

### When will V1/V2 be considered?
- Version upgrade is not based on time, but driven by **exit threshold + real data**.
- Unified roadmap: `docs/agents/VERSION_ROADMAP.md`

## Next step (must be completed)

### Next 3.1: DedupGate V0 (instances deduplication, hard access control)
- ExecPlan: `docs/agents/execplans/phase3_dedup_gate_v0.md` (written, added "bad duplication vs good duplication" alignment clause)
- Goal: keep the current `DedupReport.{json,md}` path reliable while Phase3 still uses the source-backed V0 scanner
- Current progress: the source-backed scanner entrypoint exists at `tools/dedup/dedup.py`, `nightly_dedup_instances` in `automations/registry.json` is active, and compiled-environment scanning remains follow-on work

### Next 3.2: PromotionGate V0 (minimum promotion closed loop)
- Contract: `docs/contracts/PROMOTION_GATE_CONTRACT.md` (upgraded to v0.2: advanced experience feedback)
- ExecPlan: `docs/agents/execplans/phase3_promotion_gate_v0.md` (upgraded: structural auditing and compat refinement)
- Goal: Form a rollback patch + PromotionReport (md+json), CI reads it and decides the merge

### Next 3.3: GC V0 (incubation recycling closed loop)
- Already: GCGate Contract and ExecPlan (Field Level Definition + TDD Matrix)
- Trigger: Count by domain (metric defined by contract), not by time
- Action (V0 defaults to "metadata isolation"): Mark Seeds as active/quarantined/archived in `tools/index/gc_state.json` (physical relocation/deletion will only be considered in subsequent versions)
- Output: GCReport (md+json)

Still needs to be implemented (code and automation):
- `tools/gc/gc.py` upgraded from stub to propose/apply implementation
- Reference graph construction prioritizes reuse of `import-graph`; nightly/soak optionally enables `lake shake` for semantic dependency enhancement (see `docs/reuse/GC_REUSE.md`)
- Connect GC proposal/execution to automations (dry-run + tdd + clobber)

### Next 3.4: Automations + TDD (Unattended Advisor)
- Register Promotion/GC as automation (registry)
- Each automation must have tdd (at least dry-run) and product cleanup strategy (gitignore + clobber)
- Any new external wheels: must pin + installation documentation + smoke


### Phase 6 (v0 skeleton has been implemented): real Agent eval + tutor keyword coverage (TaskPack v0)
- Contract: `docs/contracts/AGENT_EVAL_CONTRACT.md`
- Mentor keyword TaskPack v0: `docs/agents/phase6/MENTOR_KEYWORDS_TASKPACK.md`
- Machine access control (core tier):
- pack keyword coverage: `tests/agent_eval/check_pack_keyword_coverage.py`
- tasks/scenarios schema verification: `tests/agent_eval/validate_{tasks,scenarios}.py`
  - runner plan smoke:`tests/agent_eval/check_{runner,scenario_runner}_plan_mode.py`
- scenario class coverage: `tests/agent_eval/check_scenario_class_coverage.py`

Completed (Phase6.1/Phase6.2):
- ✅ fixture problem template (5 mentor keyword questions) + task.yaml variant (SUCCESS / fixable hint / TRIAGED)
- ✅ pack runner:`tools/agent_eval/run_pack.py`(plan/materialize)
- ✅ deterministic grader:`tools/agent_eval/grade_pack.py`
- ✅ scenario schema + runner:`docs/schemas/AgentEvalScenario.schema.json` + `tools/agent_eval/run_scenario.py`
- ✅ scenario grader:`tools/agent_eval/grade_scenario.py`
- ✅ maintainer fixture overlay mechanism (runner pre-applied, not counting OPERATOR patch)

Next (recommended for 6.3+):
- Connect `run` mode to real Codex/CI nightly (produce real Reports snapshot + ScenarioEvalReport)
- Expanded task library (more domains / more complex triage / more detailed patch-scope violation cases)
- Introduce visualization of pack/scenario report (trend + failure clustering)

## Memory document comparison (leakage prevention)
- `docs/agents/MEMORY_COVERAGE.md`


## Parallel discussion/parallel implementation (important)
- Comply with the parallel protocol: `docs/coordination/PARALLEL_PROTOCOL.md`
- Registration of all finalized conclusions: `docs/coordination/DECISIONS.md`
- Centralized management of open questions: `docs/coordination/OPEN_QUESTIONS.md`
