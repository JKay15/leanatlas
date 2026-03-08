# LeanAtlas AGENTS.md (Repo root, default = OPERATOR mode)

## Project navigation (read first)
- Task-to-doc map: `docs/agents/README.md`
- Current stage and "next step": `docs/agents/STATUS.md`
- Parallel workstreams protocol: `docs/coordination/PARALLEL_PROTOCOL.md`
- Decision log (single source of truth): `docs/coordination/DECISIONS.md`
- OPERATOR workflow (use-phase): `docs/agents/OPERATOR_WORKFLOW.md`
- MAINTAINER workflow (build-phase): `docs/agents/MAINTAINER_WORKFLOW.md` (and `docs/agents/PLANS.md` / `docs/agents/execplans/`)
- First-run onboarding behavior: `docs/agents/ONBOARDING.md`
- Banner source of truth: `docs/agents/BRANDING.md`
- Maintainer initialization checklist: `INIT_FOR_CODEX.md`
- Repo topology contract (3-repo + MCP boundary): `docs/contracts/REPO_TOPOLOGY_CONTRACT.md`
- Split topology setup notes: `docs/setup/SUBMODULES.md`
- Module visualization guide: `docs/tools/MODULE_VISUALIZATION.md`
- Full repository file index (low-frequency): `docs/navigation/FILE_INDEX.md`
- Review templates: `docs/review/`
- Agent-eval reference docs: `docs/agent_eval/`
- Kernel docs: `LeanAtlas/Kernel/README.md`

## First-message onboarding (mandatory for fresh clones)
<!-- ONBOARDING_BLOCK_START -->
On first prompt in a fresh clone (missing `.cache/leanatlas/onboarding/state.json`),
run `.agents/skills/leanatlas-onboard/SKILL.md` and `docs/agents/ONBOARDING.md` before any normal reply.
Also route to onboarding when state exists but `operational_ready != true` or `steps.automations != "ok"`.

Hard trigger rule:
- This applies to any first user message, including greetings like `hi`.
- Do not reply with a generic question before onboarding routing.
- First response must be: banner + A/B/C consent menu.
- Do not proceed with normal task execution until automation readiness is verified.

The full long-form onboarding block is archived at:
- `docs/agents/archive/AGENTS_ONBOARDING_VERBOSE.md`

After `bootstrap` + `doctor` both pass, root `AGENTS.md` must stay compact.
Do not re-expand this block in `AGENTS.md`.
<!-- ONBOARDING_BLOCK_END -->

Codex: You are operating LeanAtlas. The default mode is **OPERATOR**: prove new problems under `Problems/**` without changing the system (Toolbox/Incubator/tools/contracts).

## Path-scope rule for external paper sources
- LeanAtlas `AGENTS.md`, docs, and skills are path-scoped to this repository.
- If the human points Codex at a paper source outside this repository (for example a LaTeX/PDF file elsewhere on disk), LeanAtlas instructions do **not** automatically attach to that external path.
- To use LeanAtlas workflows on a repository-external paper, first ingress the source into LeanAtlas-controlled scope (for example a staged source bundle under `.cache/leanatlas/tmp/**` or a prepared `Problems/<slug>/` contract entry) and then continue from the repository root.

## Mode selection (do not guess)
- Presence or absence of root `AGENTS.override.md` is the authoritative mode selector for this repo.
- **OPERATOR (default)**: No `AGENTS.override.md` in repo root.
- **MAINTAINER**: A human created a local `AGENTS.override.md` in repo root (ignored by git). If you see it, you may modify system code, but you MUST follow the maintainer playbook.

Never create or modify `AGENTS.override.md` unless the human explicitly asked. Never commit it.

## Indexability hard rule
- Any newly added/deleted/renamed repository file must be reachable from root navigation:
  - add/update the nearest directory index (`README.md` or `AGENTS.md`), and
  - regenerate `docs/navigation/FILE_INDEX.md`.
- Any add/delete/rename of test scripts, or change to `tests/manifest.json`, must regenerate:
  - `docs/testing/TEST_MATRIX.md`.
- New files and test-registry edits are not complete unless generated-doc gates pass.

## Read-first (required)
Before editing anything, read:
- `docs/contracts/WORKFLOW_CONTRACT.md`
- `docs/contracts/REPORTING_CONTRACT.md`
- `docs/contracts/AI_NATIVE_ENGINEERING_CONTRACT.md` (vibe-coding guardrails: scope + verify + minimal diffs)
- `docs/contracts/THIRD_PARTY_DEPENDENCY_CONTRACT.md` (external deps must be pinned; MAINTAINER only)
- `docs/agents/GLOSSARY.md`
- If the task is large/architectural: `docs/agents/PLANS.md` (ExecPlans)

## AI-native ("vibe coding") guardrails

You MAY move fast, but you MUST keep the seatbelt on:

- Always state **scope + verification commands** before writing code.
- Prefer TDD: make a failing check, then the smallest fix, then verify.
- If you cannot run verification, explicitly state what would be run and why it wasn't.
- Keep patches minimal and local; avoid opportunistic refactors.

## OPERATOR hard boundaries (PatchScope)
When in OPERATOR mode you MAY edit only inside a single problem folder:

Allowed edits (default):
- `Problems/<problem_slug>/Proof.lean`
- `Problems/<problem_slug>/Cache.lean` and `Problems/<problem_slug>/Cache/**`
- `Problems/<problem_slug>/Scratch.lean` (may contain `sorry`, isolated)

Forbidden edits (always TRIAGED in OPERATOR):
- `Problems/<problem_slug>/Spec.lean`
- Anything under `LeanAtlas/**`, `tools/**`, `docs/contracts/**`, `.github/**`
- Any file outside the active `Problems/<problem_slug>/` directory

If you need to change forbidden files, stop and output TRIAGED with evidence + a concrete maintainer plan.

## Required outputs (every attempt/run)
For every run of the small loop, produce the reporting triple:
- `RunReport.json` + `RunReport.md`
- `RetrievalTrace.json`
- `AttemptLog.jsonl`

They MUST conform to:
- `docs/contracts/REPORTING_CONTRACT.md`
- `docs/contracts/THIRD_PARTY_DEPENDENCY_CONTRACT.md` (external deps must be pinned; MAINTAINER only)
- `docs/schemas/RunReport.schema.json`
- `docs/schemas/RetrievalTrace.schema.json`
- `docs/schemas/AttemptLogLine.schema.json`

## Test commands (local dev)
Fast deterministic gates:
- `lake lint` (preferred)
- `lake test` (preferred)
- `python tests/run.py --profile core` (equivalent)

Execution tests (requires Lean + mathlib installed locally):
- `python tests/e2e/run_cases.py --profile smoke`
- `python tests/e2e/run_cases.py --profile core`
- `python tests/e2e/run_scenarios.py --profile core`

Cleaning (must keep repo lean):
- `./scripts/clean.sh`  (safe)
- `./scripts/clobber.sh` (nuclear)

## Skills
This repo includes skills under `.agents/skills/`. Prefer invoking them for repeatable workflows (proof loop, triage reporting, running scenarios).
Skill-specific docs index: `.agents/skills/docs/`.
