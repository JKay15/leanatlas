# Codex Document System (LeanAtlas)

This directory is for documentation "for Codex use" (not for human-readable essays).

## Start here
- First-run onboarding (welcome + consented setup): `docs/agents/ONBOARDING.md`
- Current LOOP mainline system: `docs/agents/LOOP_MAINLINE.md`
- Banner/source style: `docs/agents/BRANDING.md`
- Maintainer initialization checklist: `INIT_FOR_CODEX.md`
- Full file-level index (low-frequency lookup): `docs/navigation/FILE_INDEX.md`

## Why do we need a "document system"?
The goal of LeanAtlas is not to write a piece of Lean code, but to make Codex work stably for a long time in real projects:
- Have clear boundaries (which files can be changed and which cannot be changed)
- Have reproducible exit criteria (SUCCESS/TRIAGED)
- There are mandatory audit products (RunReport / RetrievalTrace / AttemptLog)
- Has testable access control (TDD)

## Task → Which documents should be read (quick entry, ≤8 lines)

| Tasks | Which documents to read first (in order) |
|---|---|
| First-run onboarding (welcome + consented setup) | `docs/agents/ONBOARDING.md` → `.agents/skills/leanatlas-onboard/SKILL.md` → `INIT_FOR_CODEX.md` → `docs/setup/QUICKSTART.md` |
| Prove a problem (natural language → SUCCESS/TRIAGED) | `docs/agents/OPERATOR_WORKFLOW.md` → `docs/contracts/WORKFLOW_CONTRACT.md` → `docs/contracts/RUNREPORT_CONTRACT.md` → `docs/contracts/RETRIEVAL_TRACE_CONTRACT.md` → `.agents/skills/leanatlas-operator-proof-loop/SKILL.md` |
| Understand/use the current mainline LOOP system | `docs/agents/LOOP_MAINLINE.md` → `.agents/skills/leanatlas-loop-mainline/SKILL.md` → `.agents/skills/loop-review-reconciliation/SKILL.md` when the task is authoritative finding settlement → `docs/agents/MAINTAINER_WORKFLOW.md` or `docs/agents/OPERATOR_WORKFLOW.md` depending on mode |
| Update/extend domain dictionary (MSC2020/LOCAL) | `docs/contracts/MCP_MSC2020_CONTRACT.md` → `docs/setup/external/msc2020.md` → `tools/lean_domain_mcp/**` → `.agents/skills/leanatlas-domain-mcp/SKILL.md` |
| Run automations (backend Advisor) | `docs/agents/AUTOMATIONS.md` → `docs/contracts/AUTOMATION_CONTRACT.md` → `automations/registry.json` → `.agents/skills/leanatlas-automations/SKILL.md` |
| Deposit and route chat feedback | `docs/agents/FEEDBACK_LOOP.md` → `tools/feedback/mine_chat_feedback.py` → `automations/registry.json` (`nightly_chat_feedback_deposition`) |
| Maintain Dedup/Promotion/GC closed loop (Phase3) | `docs/agents/MAINTAINER_WORKFLOW.md` → `docs/agents/execplans/phase3_*` → `docs/contracts/PROMOTION_GATE_CONTRACT.md`/`GC_*` → `.agents/skills/leanatlas-dedup|promote|gc/SKILL.md` |
| Maintain LOOP runtime contracts (provider routing / review-history / SDK-MCP alignment) | `docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md` → `docs/contracts/LOOP_PYTHON_SDK_CONTRACT.md` + `docs/contracts/LOOP_MCP_CONTRACT.md` → `docs/schemas/WaveExecutionLoopRun.schema.json` + `docs/schemas/LoopSDKCallContract.schema.json` → `.agents/skills/loop-review-reconciliation/SKILL.md` first for generic authoritative finding settlement semantics → `.agents/skills/leanatlas-loop-maintainer-ops/SKILL.md` for LeanAtlas-local wiring |
| Accelerate maintainer AI review (scope partition / staged narrowing / pyramid reviewer) | `docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md` → `docs/contracts/LOOP_PYTHON_SDK_CONTRACT.md` → `tools/loop/review_strategy.py` → `.agents/skills/leanatlas-loop-review-acceleration/SKILL.md` |
| Phase6: Real Agent eval (without relying on vibe) | `docs/contracts/AGENT_EVAL_CONTRACT.md` → `docs/agents/EVAL_PROBLEM_PACK_GUIDE.md` → `tools/agent_eval/run_pack.py`/`grade_pack.py` + `tools/agent_eval/run_scenario.py`/`grade_scenario.py` → `.agents/skills/leanatlas-agent-eval/SKILL.md` |
| Phase6: Design real question set (ProblemPack/Scenario) | `docs/agents/EVAL_PROBLEM_PACK_GUIDE.md` → `tests/agent_eval/packs/**` + `tests/agent_eval/scenarios/**` → `docs/contracts/AGENT_EVAL_CONTRACT.md` |
| Install/lock external "wheels" | `docs/setup/DEPENDENCIES.md` → `docs/contracts/THIRD_PARTY_DEPENDENCY_CONTRACT.md` → `tools/deps/pins.json` |

## Codex How to read instructions (AGENTS.md)
Codex builds a "chain of instructions" at the start of a run:
- Read at most one file in each directory: `AGENTS.override.md` first, otherwise `AGENTS.md`
- Go all the way from the warehouse root directory to the current working directory, and splice together the instructions along the way.
- The closer the directive is to the current directory, the more it "covers" the upper layer (because it appears further back)

therefore:
- The root directory `AGENTS.md` must be short and only contain global hard rules.
- Specific rules should be placed in subdirectories close to the code (such as `Problems/AGENTS.md`, `tests/AGENTS.md`)
- Maintainers can temporarily switch to MAINTAINER mode using local `AGENTS.override.md` (the file must be in gitignore)
- No override is auto-enabled by default: templates under `docs/agents/templates/` only become active after explicit manual copy to root `AGENTS.override.md`

## Directory description
- `STATUS.md`: current stage status and next step (single source of truth)
- `LOOP_MAINLINE.md`: canonical entry for the committed mainline LOOP system
- `OPERATOR_WORKFLOW.md`: lifetime workflow (from natural language questions to SUCCESS/TRIAGED)
- `MAINTAINER_WORKFLOW.md`: Maintenance period workflow skeleton (system evolution, ExecPlan driver)
- `PLANS.md`: ExecPlan specification (for complex changes/refactorings/new modules)
- `GLOSSARY.md`: Glossary of terms (undefined terms are prohibited)
- `templates/`: Optional templates (manual opt-in only; not auto-applied)
  - `templates/AGENTS.override.md`: full MAINTAINER local override template
  - `templates/AGENTS.override.minimal.md`: compact local override template
  - Includes post-onboarding automation install template: `templates/AUTOMATION_INSTALL_CHECKLIST.md`

## External dependencies and installation (don’t let Codex guess blindly)
- Summary list of external dependencies: `docs/setup/DEPENDENCIES.md`
- MCP (lean-lsp-mcp) installation: `docs/setup/external/lean-lsp-mcp.md`
- Depends on smoke (nightly): `python tests/run.py --profile nightly`

## Important agreement: Do not pollute the main library with "test temporary injection"
Any test that needs to temporarily put something into the Toolbox/Incubator must be injected into the working directory of `.cache/leanatlas/**` through the "workspace overlay" of the test runner.
It is forbidden to write test-only content into the real `LeanAtlas/**`, and `git status --porcelain` must be empty after the test is completed.
