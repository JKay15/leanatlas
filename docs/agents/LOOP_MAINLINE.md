# LOOP Mainline in LeanAtlas

This is the canonical entry for the current mainline LOOP system in LeanAtlas.

Use this page when you need to answer any of these questions:
- what parts of LOOP are already implemented in mainline
- which parts are only partial or still planned
- where `LOOP core` stops and `LeanAtlas adapters` start
- which docs, tools, tests, and skills are the default entrypoints
- how experimental `.cache/leanatlas/tmp/**` assets relate to the committed mainline

## Quick entrypoints

- Maintainer/system changes:
  - `docs/agents/MAINTAINER_WORKFLOW.md`
  - `tools/loop/maintainer.py`
  - `.agents/skills/leanatlas-loop-mainline/SKILL.md`
- Review/routing specifics:
  - `tools/loop/review_runner.py`
  - `tools/loop/review_strategy.py`
  - `tools/loop/review_orchestration.py`
  - `.agents/skills/leanatlas-loop-review-acceleration/SKILL.md`
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
| Default automated review execution | Partial | `tools/loop/review_runner.py`, `tools/loop/review_orchestration.py` | Single-review execution is implemented; default staged `FAST -> DEEP -> STRICT` execution is not yet the automatic path. |
| LOOP core vs LeanAtlas adapter layering | Implemented | `docs/contracts/LOOP_RUNTIME_CONTRACT.md`, `docs/agents/execplans/20260307_loop_core_parallel_nested_batch_v0.md` | Core is role-neutral; host/workflow semantics stay in adapters. |
| Batch supervisor / autopilot | Planned | `docs/agents/execplans/20260307_batch_supervisor_autopilot_and_human_ingress_v0.md` | Parent-loop automation across child waves is not landed yet. |
| Review supersession / reconciliation runtime | Planned | `docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md` | Contract direction exists; runtime/evidence engine is still follow-on work. |
| Capability publish + context refresh | Planned | `docs/agents/execplans/20260307_loop_core_parallel_nested_batch_v0.md` | Future loops must adopt new capabilities through explicit publish/rematerialize steps. |
| LeanAtlas worktree orchestration | Planned | `docs/coordination/WORKSTREAMS.md`, `docs/agents/execplans/20260307_loop_core_parallel_nested_batch_v0.md` | Worktree coordination is documented, but not yet a LOOP-native execution layer. |
| OPERATOR / MAINTAINER workflow integration on the new core | Partial | `docs/agents/OPERATOR_WORKFLOW.md`, `docs/agents/MAINTAINER_WORKFLOW.md` | Workflows reference LOOP surfaces, but full adapter integration is still staged. |

## LOOP core vs LeanAtlas adapters

### LOOP core

`LOOP core` is the role-neutral execution/evidence layer under `tools/loop/**`.

It includes:
- graph composition semantics (`serial`, `parallel`, `nested`, `race`, `quorum`, `barrier`)
- runtime execution and scheduler evidence
- review/evidence payload normalization
- stable maintainer session bookkeeping and closeout refs
- resource-arbiter rules and contracts

### LeanAtlas adapters

LeanAtlas adapters are project/workflow layers built on top of LOOP core.

They include:
- MAINTAINER workflow integration
- OPERATOR workflow integration
- review acceleration/pyramid-review usage policies
- future worktree orchestration
- future batch supervisor/autopilot over LeanAtlas-specific waves

The rule is:
- `LOOP core` must stay role-neutral
- `MAINTAINER`, `OPERATOR`, and `worktree` semantics must stay in LeanAtlas adapter/workflow docs

## How to use the current mainline

### Maintainer path

Use this path when you are changing system code, LOOP behavior, contracts, tests, or skills:
- read `docs/agents/MAINTAINER_WORKFLOW.md`
- use `.agents/skills/leanatlas-loop-mainline/SKILL.md` for routing/orientation
- use `.agents/skills/leanatlas-maintainer-execplan/SKILL.md` for non-trivial changes
- use `.agents/skills/leanatlas-loop-maintainer-ops/SKILL.md` when the change is LOOP-specific

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
- `.agents/skills/README.md`
- `docs/testing/TEST_MATRIX.md`
- `docs/navigation/FILE_INDEX.md`
