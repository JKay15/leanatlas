---
title: Whole-project health audit with true parallel reviewer-of-reviewer experiment
owner: Codex (local workspace)
status: active
created: 2026-03-08
---

## Purpose / Big Picture
This wave is an audit-only maintainer pass over the current LeanAtlas whole-project mainline. The goal is to re-evaluate the repository's project-level workflows, LOOP mainline surfaces, formalization platform, Phase3 gates, Phase6 eval surfaces, and routing/discoverability layers on the current branch without implementing repairs. The first output is a fresh primary audit matrix that answers whether mainline entrypoints, contracts, tests, skills, and closeout evidence still line up on current repository bytes rather than prior thread memory. The second output is a true parallel reviewer-of-reviewer experiment in which four independent reviewers audit the primary audit artifact itself, not the codebase, and then reconcile their conclusions. If true parallel review cannot be demonstrated with overlapping execution evidence, the experiment must be reported as blocked rather than approximated.

## Glossary
- `primary audit`: the first-layer whole-project health matrix produced from direct repository inspection and read-only verification.
- `reviewer-of-reviewer` (`RoR`): a second-layer review that only inspects the primary audit artifact and its cited evidence, not the repository code/docs directly.
- `true parallel`: four independent reviewer processes running with separate sessions and overlapping execution windows that can be evidenced from artifacts or runtime metadata.
- `contamination`: any limitation introduced by pre-existing uncommitted worktree changes that may affect verification results or the interpretation of findings.
- `baseline finding`: a retained project-health conclusion that is supported by current repository evidence and survives RoR reconciliation.

## Scope
In scope:
- create and maintain this audit-only ExecPlan
- read the project-level docs, contracts, skills, and tool surfaces named in the task
- generate a fresh whole-project primary audit artifact
- run read-only verification commands requested by the user
- record contamination from pre-existing worktree modifications when it affects validation or confidence
- run four independent true-parallel RoR branches against the primary audit artifact only
- reconcile the four RoR outputs into one summary with retain/downgrade/withdraw decisions

Out of scope:
- modifying system code under `LeanAtlas/**`, `tools/**`, `tests/**`, `docs/contracts/**`, or any other implementation surface
- repairing findings discovered by the audit
- converting the RoR experiment into a repair wave or feature implementation
- pretending sequential execution is parallel

Allowed changes:
- `docs/agents/execplans/20260308_parallel_ror_whole_project_audit_v0.md`
- `artifacts/verify/20260308_parallel_ror_whole_project_*`
- `artifacts/reviews/20260308_parallel_ror_whole_project_*`

Forbidden changes:
- repository implementation files, schemas, tests, contracts, or committed workflow docs outside this ExecPlan

## Interfaces and Files
- `docs/agents/PLANS.md`: ExecPlan requirements.
- `docs/agents/STATUS.md`
- `docs/agents/README.md`
- `docs/agents/LOOP_MAINLINE.md`
- `docs/agents/MAINTAINER_WORKFLOW.md`
- `docs/agents/OPERATOR_WORKFLOW.md`
- `docs/agents/ONBOARDING.md`
- `docs/agents/AUTOMATIONS.md`
- `docs/contracts/FORMALIZATION_LEDGER_CONTRACT.md`
- `docs/contracts/FORMALIZATION_GOVERNANCE_CONTRACT.md`
- `docs/contracts/LOOP_RUNTIME_CONTRACT.md`
- `docs/contracts/LOOP_GRAPH_CONTRACT.md`
- `docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md`
- `docs/contracts/LOOP_PYTHON_SDK_CONTRACT.md`
- `tools/formalization/**`
- `tools/workflow/formalization_governor.py`
- `tools/loop/**`
- `.agents/skills/README.md`
- `.agents/skills/leanatlas-operator-proof-loop/SKILL.md`
- `.agents/skills/leanatlas-agent-eval/SKILL.md`
- `.agents/skills/leanatlas-automations/SKILL.md`
- `.agents/skills/leanatlas-loop-mainline/SKILL.md`
- `.agents/skills/leanatlas-loop-maintainer-ops/SKILL.md`
- Phase3 surfaces:
  - `.agents/skills/leanatlas-dedup/SKILL.md`
  - `.agents/skills/leanatlas-promote/SKILL.md`
  - `.agents/skills/leanatlas-gc/SKILL.md`
  - `tools/dedup/**`
  - `tools/promote/**`
  - `tools/gc/**`
  - related docs/contracts/tests discovered during audit
- planned output artifacts:
  - `artifacts/verify/20260308_parallel_ror_whole_project_primary_audit.md`
  - `artifacts/verify/20260308_parallel_ror_whole_project_reconciliation_summary.md`
  - `artifacts/reviews/20260308_parallel_ror_whole_project_*`

## Milestones
### 1) Freeze audit scope and gather mainline authority
Deliverables:
- this ExecPlan
- a frozen list of mainline materials and verification commands
- a contamination note based on the pre-existing dirty worktree

Commands:
- `git branch --show-current`
- `git status --short`
- `sed -n '1,240p' docs/agents/PLANS.md`
- `sed -n '1,240p'` on the required docs/contracts/skills/tool entrypoints

Acceptance:
- branch and dirty-worktree state are recorded before substantive audit work
- required mainline entry docs are identified before conclusions are written

### 2) Produce a fresh primary whole-project audit matrix
Deliverables:
- `artifacts/verify/20260308_parallel_ror_whole_project_primary_audit.md`

Commands:
- `rg --files` / `sed -n` / targeted `uv run --locked python tests/contract/...` checks as needed
- no write-back commands against repository implementation surfaces

Acceptance:
- the matrix covers all ten required audit bands from the user request
- each band states mainline entry clarity, docs/contracts/tests/skills alignment, implemented-vs-partial drift, discoverability, and evidence/closeout gaps
- findings are tied to concrete file/test evidence

### 3) Run requested read-only verification
Deliverables:
- verification notes embedded in the audit artifact or companion review artifacts

Commands:
- `uv run --locked python tests/run.py --profile core`
- `uv run --locked python tests/run.py --profile nightly`
- `lake build`
- `git diff --check`

Acceptance:
- command outcomes are captured
- any contamination from pre-existing modified files is recorded explicitly

### 4) Run four true-parallel reviewer-of-reviewer branches
Deliverables:
- four independent RoR evidence chains, each with unique `review_id`, prompt, response, summary, canonical payload, and attempts evidence
- runtime evidence showing overlapping execution windows or sessions

Commands:
- four independently launched reviewer commands against the primary audit artifact only
- polling/collection commands for session completion and artifact timestamps

Acceptance:
- the four reviewer processes are demonstrably concurrent
- if concurrency cannot be shown, mark this milestone blocked instead of fabricating a result

### 5) Reconcile RoR outputs and answer final audit questions
Deliverables:
- `artifacts/verify/20260308_parallel_ror_whole_project_reconciliation_summary.md`
- final retained/downgraded/withdrawn primary findings
- explicit answers to the user's five closing questions

Commands:
- `sed -n` / `cat` over RoR outputs and verification notes
- no repository implementation changes

Acceptance:
- reconciliation names consensus, disagreements, retained findings, downgraded findings, withdrawn findings, primary-audit trust level, and whether RoR added value

## Testing plan (TDD)
This is an audit-only wave. There are no implementation changes and therefore no new tests to write first. Verification consists of:
- direct inspection of the named docs/contracts/skills/tools surfaces
- read-only execution of the requested validation commands
- read-only execution of reviewer commands that only consume the primary audit artifact and write review artifacts under `artifacts/**`
- contamination tracking for any validation affected by unrelated pre-existing worktree changes

## Decision log
- 2026-03-08: treat this task as audit-only; findings may be triaged and prioritized, but not repaired here.
- 2026-03-08: primary audit must be regenerated fresh from repository state rather than copied from previous thread artifacts.
- 2026-03-08: reviewer-of-reviewer branches are constrained to the primary audit artifact and cited evidence only; they must not silently expand back into code review.
- 2026-03-08: true parallel is mandatory; a sequential fallback is not acceptable for this experiment.

## Rollback plan
- If this audit bundle must be discarded, remove:
  - `docs/agents/execplans/20260308_parallel_ror_whole_project_audit_v0.md`
  - `artifacts/verify/20260308_parallel_ror_whole_project_*`
  - `artifacts/reviews/20260308_parallel_ror_whole_project_*`
- Verify rollback by confirming `git status --short` no longer shows those paths.

## Outcomes & retrospective (fill when done)
- Pending.
