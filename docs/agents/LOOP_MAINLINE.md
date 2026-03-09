# LOOP Mainline in LeanAtlas

This is the canonical entry for the current mainline LOOP system in LeanAtlas.

Use this page when you need to answer any of these questions:
- what parts of LOOP are already implemented in mainline
- which parts are only partial or still planned
- where `LOOP core` stops and `LeanAtlas adapters` start
- how the root supervisor kernel relates to layered supervisor execution
- which docs, tools, tests, and skills are the default entrypoints
- how experimental `.cache/leanatlas/tmp/**` assets relate to the committed mainline

## Quick entrypoints

- Maintainer/system changes:
  - `docs/agents/MAINTAINER_WORKFLOW.md`
  - `tools/loop/maintainer.py`
  - `.agents/skills/leanatlas-loop-mainline/SKILL.md`
- Standalone/non-LeanAtlas usage:
  - `docs/setup/LOOP_LIBRARY_QUICKSTART.md`
  - `looplib/__init__.py`
  - `.agents/skills/loop-mainline/SKILL.md`
  - `.agents/skills/loop-review-orchestration/SKILL.md`
  - `.agents/skills/loop-batch-supervisor/SKILL.md`
- Review/routing specifics:
  - `tools/loop/review_runner.py`
  - `tools/loop/review_strategy.py`
  - `tools/loop/review_orchestration.py`
  - `tools/loop/review_reconciliation.py`
  - `.agents/skills/loop-review-reconciliation/SKILL.md`
  - `.agents/skills/leanatlas-loop-review-acceleration/SKILL.md`
- Parent supervision / publication / context refresh:
  - `tools/loop/batch_supervisor.py`
  - `tools/loop/publication.py`
  - `tools/loop/worktree_adapter.py`
- Formalization front-end helpers:
  - `tools/formalization/external_source_pack.py`
  - `tools/formalization/source_enrichment.py`
  - `tools/formalization/review_todo.py`
  - `tools/formalization/resync_reverse_links.py`
- Core contracts:
  - `docs/contracts/LOOP_RUNTIME_CONTRACT.md`
  - `docs/contracts/LOOP_GRAPH_CONTRACT.md`
  - `docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md`
  - `docs/contracts/LOOP_PYTHON_SDK_CONTRACT.md`
- Operator/use-phase boundary:
  - `docs/agents/OPERATOR_WORKFLOW.md`

## Capability Matrix

| Surface | Status | Main references | Notes |
|---|---|---|---|
| LOOP core graph/runtime contracts | Implemented | `docs/contracts/LOOP_RUNTIME_CONTRACT.md`, `docs/contracts/LOOP_GRAPH_CONTRACT.md`, `docs/contracts/LOOP_RESOURCE_ARBITER_CONTRACT.md` | Canonical semantics live in committed contracts and tests. |
| Native parallel runtime + nested lineage | Implemented | `tools/loop/graph_runtime.py`, `tests/contract/check_loop_graph_parallel_nested_runtime.py` | Core runtime now consumes parallel scheduling limits and emits nested-lineage evidence. |
| Maintainer LOOP session + stable closeout ref | Implemented | `tools/loop/maintainer.py`, `artifacts/loop_runtime/by_execplan/**/MaintainerCloseoutRef.json` | ExecPlans can cite settled-state maintainer closeout without run-key recursion. |
| Review strategy helpers (partitioning / narrowing / pyramid planning) | Implemented | `tools/loop/review_strategy.py`, `.agents/skills/leanatlas-loop-review-acceleration/SKILL.md` | Deterministic planning aids are committed and tested. |
| Review orchestration graph/bundle compilation | Implemented | `tools/loop/review_orchestration.py`, `docs/agents/execplans/20260307_review_orchestration_automation_v0.md` | The compiler/bundle layer exists in mainline. |
| User preference presets | Implemented | `tools/loop/user_preferences.py`, `docs/agents/ONBOARDING.md`, `docs/setup/QUICKSTART.md` | Presets are committed, stored at `.cache/leanatlas/onboarding/loop_preferences.json`, auto-staged on demand, and consumed by the default review-orchestration helper path. |
| Default automated review execution | Implemented | `tools/loop/review_orchestration.py`, `tests/contract/check_loop_review_automation_runtime.py` | `build_default_review_orchestration_bundle(...)` and `execute_review_orchestration_bundle(...)` materialize the committed default staged-review path and triage non-reconcilable reviewer output instead of corrupting reconciliation state. |
| LOOP core vs LeanAtlas adapter layering | Implemented | `docs/contracts/LOOP_RUNTIME_CONTRACT.md`, `docs/agents/execplans/20260307_loop_core_parallel_nested_batch_v0.md` | Core is role-neutral; host/workflow semantics stay in adapters. |
| Batch supervisor / autopilot | Implemented | `tools/loop/batch_supervisor.py`, `tests/contract/check_loop_batch_supervisor.py`, `docs/agents/execplans/20260307_batch_supervisor_autopilot_and_human_ingress_v0.md` | Parent supervisors now materialize child waves, reroute retryable failures, and publish integrated closeout evidence. |
| Independent LOOP Python library extraction / packaging | Implemented | `looplib/__init__.py`, `docs/setup/LOOP_LIBRARY_QUICKSTART.md`, `examples/looplib_quickstart.py`, `docs/agents/execplans/20260308_loop_python_library_decoupling_packaging_v0.md` | Reusable in-repo `looplib` imports, standalone docs, and generic skills now exist for non-LeanAtlas hosts; host-specific worktree adapters remain lazy optional dependencies. |
| Review supersession / reconciliation runtime | Implemented | `tools/loop/review_reconciliation.py`, `docs/schemas/ReviewSupersessionReconciliation.schema.json`, `.agents/skills/loop-review-reconciliation/SKILL.md`, `tests/contract/check_loop_review_reconciliation_runtime.py`, `docs/agents/execplans/20260308_review_supersession_reconciliation_runtime_v0.md` | Deterministic authoritative reconciliation artifacts and persistence are landed, including run-key-independent immutable ledgers, authoritative finding settlement, and medium-reviewed closeout evidence. |
| Capability publish + context refresh | Implemented | `tools/loop/publication.py`, `tests/contract/check_loop_publication_runtime.py` | Capability publication, human ingress, and rematerialized context packs are explicit append-only runtime artifacts. |
| LeanAtlas worktree orchestration | Implemented | `tools/loop/worktree_adapter.py`, `tests/contract/check_loop_worktree_adapter.py` | LeanAtlas worktree orchestration now exists as a host adapter layered on top of LOOP core and batch supervision. |
| OPERATOR / MAINTAINER workflow integration on the new core | Implemented | `docs/agents/OPERATOR_WORKFLOW.md`, `docs/agents/MAINTAINER_WORKFLOW.md`, `docs/agents/execplans/20260308_loop_master_plan_completion_wave_v0.md` | Workflow docs now route through the committed mainline core, default review execution, batch supervision, and adapter boundaries. |
| Formalization front-end helpers | Implemented | `tools/formalization/external_source_pack.py`, `tools/formalization/source_enrichment.py`, `tools/formalization/review_todo.py`, `tools/formalization/resync_reverse_links.py` | Committed ingress/enrichment helpers absorb high-value paper-workflow capabilities from `.cache` experiments. |

## LOOP core vs LeanAtlas adapters

Supervisor-first default:
- generic non-trivial LOOP execution starts from a root supervisor kernel
- layered supervisor execution then fans out into wave supervisors, subgraph supervisors, and workers
- integrated closeout authority returns to the root rather than staying with any delegated worker lane

### LOOP core

`LOOP core` is the role-neutral execution/evidence layer under `tools/loop/**`.

It includes:
- graph composition semantics (`serial`, `parallel`, `nested`, `race`, `quorum`, `barrier`)
- runtime execution and scheduler evidence
- review/evidence payload normalization
- resource-arbiter rules and contracts

### LeanAtlas adapters

LeanAtlas adapters are project/workflow layers built on top of LOOP core.

They include:
- MAINTAINER workflow integration
- OPERATOR workflow integration
- stable maintainer session bookkeeping and closeout refs
- LeanAtlas wrapper mapping: conversation Codex = root supervisor kernel
- review acceleration/pyramid-review usage policies
- worktree orchestration
- batch supervisor/autopilot over LeanAtlas-specific waves

The rule is:
- `LOOP core` must stay role-neutral
- `MAINTAINER`, `OPERATOR`, and `worktree` semantics must stay in LeanAtlas adapter/workflow docs

## How to use the current mainline

## User preference presets

The committed local artifact path for post-onboarding LOOP defaults is:
- `.cache/leanatlas/onboarding/loop_preferences.json`

Supported presets:
- `Budget Saver`
  - current default reviewer path: `FAST + low`
  - current default reviewer tier policy: `LOW_PLUS_MEDIUM`
  - keep this unless the task justifies more review cost
- `Balanced`
- `Auditable`

These presets are post-onboarding defaults, not bootstrap blockers. The committed mainline surface now provides the preset names, artifact shape, auto-staging helper, and override semantics through `tools/loop/user_preferences.py`. The default staged review path consumes that artifact automatically through `build_default_review_orchestration_bundle(...)`, while later runs may still override any chosen defaults without mutating the stored preference artifact.

Current default policy:
- `Budget Saver` is the committed default preset.
- `FAST + low` is the default reviewer path.
- `LOW_PLUS_MEDIUM` is the committed default reviewer tier policy.
- `medium` is the standard bounded escalation tier.
- `medium` is a bounded escalation only for small-scope high-risk core logic.
- `STRICT / xhigh` remains available for exceptional audit-heavy closeout, but it is not the default path.

## Standalone LOOP path

For reusable/non-LeanAtlas usage:
- start with `docs/setup/LOOP_LIBRARY_QUICKSTART.md`
- import from `looplib`
- route generic questions through `.agents/skills/loop-mainline/SKILL.md`
- route staged review work through `.agents/skills/loop-review-orchestration/SKILL.md`
- route parent-wave supervision or publication/rematerialization through `.agents/skills/loop-batch-supervisor/SKILL.md`

This surface is intentionally separate from LeanAtlas-specific workflow adapters.

## Parent supervisor path

Use this path when the task needs more than one child wave:
- materialize the parent batch via `tools/loop/batch_supervisor.py`
- publish new capabilities or bounded human input via `tools/loop/publication.py`
- rematerialize downstream context before later child-wave adoption
- use `tools/loop/worktree_adapter.py` only when the host needs isolated git workspaces

### Maintainer path

Use this path when you are changing system code, LOOP behavior, contracts, tests, or skills:
- read `docs/agents/MAINTAINER_WORKFLOW.md`
- use `.agents/skills/leanatlas-loop-mainline/SKILL.md` for routing/orientation
- use `.agents/skills/leanatlas-maintainer-execplan/SKILL.md` for non-trivial changes
- use `.agents/skills/loop-review-reconciliation/SKILL.md` first when the task is authoritative finding settlement and should stay role-neutral
- use `.agents/skills/leanatlas-loop-maintainer-ops/SKILL.md` when the change is LOOP-specific LeanAtlas wiring rather than generic reconciliation semantics

### Operator path

Use this path when you are solving a problem inside `Problems/**` without changing system code:
- read `docs/agents/OPERATOR_WORKFLOW.md`
- keep system changes out of scope
- treat LOOP system docs as context for boundaries, not permission to edit maintainer-only code

## Experimental asset classification

`.cache/leanatlas/tmp/**` is not a bulk-copy source for mainline. Treat it as one of three classes:

| Class | Meaning | Current examples |
|---|---|---|
| Absorbed capability source | The experiment informed a committed mainline capability and should now be cited only as origin/history. | `.cache/leanatlas/tmp/loop_architecture_proto_v0_1`, `.cache/leanatlas/tmp/theorem_proof_proto_v0_2`, `.cache/leanatlas/tmp/arxiv_2112_13254v3_proto_v0_3` |
| Retained evidence / fixture input | Keep as audit sample, replay input, or regression fixture source. | `.cache/leanatlas/tmp/worktree_audit_20260305`, `.cache/leanatlas/tmp/waveB_codex_review_scope_*`, `.cache/leanatlas/tmp/wave_review_closure_scope_*` |
| Experimental-only material | Paper/workspace-specific ledgers, local workspaces, and ad hoc SOP glue that should remain outside canonical mainline paths. | paper-specific `lean_work/**`, temporary review workspaces, local-only prototype ledgers |

Mainline absorption rule:
- replace or upgrade committed capabilities based on validated experimental ideas
- do not wholesale copy `.cache/leanatlas/tmp/**` into committed mainline paths

## Project-level integration checklist

If LOOP gains or changes a mainline capability, keep these aligned:
- `docs/agents/STATUS.md`
- `docs/agents/README.md`
- `docs/agents/MAINTAINER_WORKFLOW.md`
- `docs/agents/OPERATOR_WORKFLOW.md`
- `docs/setup/LOOP_LIBRARY_QUICKSTART.md`
- `.agents/skills/README.md`
- `docs/testing/TEST_MATRIX.md`
- `docs/navigation/FILE_INDEX.md`
