---
title: Stage LOOP Python library extraction, packaging, and non-LeanAtlas usage docs
owner: Codex (local workspace)
status: done
created: 2026-03-08
parent_execplan: docs/agents/execplans/20260307_loop_core_parallel_nested_batch_v0.md
---

## Purpose / Big Picture
LeanAtlas now treats LOOP as a committed mainline system, but that alone is not enough if LOOP is also expected to become a reusable Python library for other Codex projects. The current repository already distinguishes `LOOP core` from `LeanAtlas adapters`, but that boundary is still mostly documented inside the LeanAtlas host project. This plan makes the cross-project requirement explicit: LOOP should eventually be extractable and packageable as an independent Python library with its own usage docs, while LeanAtlas remains one concrete host/adaptor environment built on top of it.

This plan does not say "copy the current repo into a package immediately." It stages the work needed so later implementation can deliver a real standalone library surface rather than a vague decoupling promise.

## Scope
In scope:
- define the future independent LOOP Python library boundary
- define what must move into the reusable library vs what remains LeanAtlas-specific
- stage packaging/docs/examples requirements for non-LeanAtlas users
- stage the corresponding generic LOOP skill surface needed by non-LeanAtlas users
- define compatibility expectations for other Codex projects consuming the library

Out of scope:
- performing the full extraction in this planning wave
- publishing a package to PyPI in this planning wave
- forcing current LeanAtlas paths to stop working before the library boundary is implemented

## Target boundary
Reusable library candidates:
- graph composition/runtime semantics
- scheduler / nested-lineage evidence model
- canonical review payload normalization
- provider-neutral review orchestration planning surface
- generic resource-arbiter support
- generic loop/session evidence helpers where role-neutral

LeanAtlas-specific adapters that should remain outside the reusable library:
- `MAINTAINER` / `OPERATOR` workflow semantics
- worktree orchestration as a LeanAtlas host strategy
- AGENTS.md-chain conventions and LeanAtlas-specific instruction-scope derivation
- LeanAtlas-specific artifact roots and project-level workflow docs
- formalization workflow glue that is specific to LeanAtlas paper tooling

## Interfaces and Files
- `tools/loop/**`
- `docs/contracts/LOOP_RUNTIME_CONTRACT.md`
- `docs/contracts/LOOP_GRAPH_CONTRACT.md`
- `docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md`
- `docs/contracts/LOOP_PYTHON_SDK_CONTRACT.md`
- `docs/agents/LOOP_MAINLINE.md`
- `docs/agents/MAINTAINER_WORKFLOW.md`
- `docs/agents/OPERATOR_WORKFLOW.md`
- future packaging/docs/example paths to be decided during implementation

## Milestones
1) Freeze the extraction boundary
- Deliverables:
  - one authoritative split between reusable LOOP library surfaces and LeanAtlas adapters
  - explicit list of current coupling points that block extraction
- Acceptance:
  - the project no longer relies on "bounded decoupling" as a proxy for real cross-project reuse

2) Stage packaging requirements
- Deliverables:
  - define package/module layout expectations
  - define how contracts/schemas/examples ship with the reusable library
  - define what a minimal non-LeanAtlas consumer must install and configure
- Acceptance:
  - another Codex project could, in principle, consume the planned package without importing LeanAtlas-only workflow semantics

3) Stage docs/examples requirements
- Deliverables:
  - define library quickstart expectations
  - define examples for maintainer-like and operator-like host usage without LeanAtlas coupling
  - define the generic LOOP skills that those docs/examples route through
  - define how current LeanAtlas mainline docs point to the future library boundary
- Acceptance:
  - "usable outside LeanAtlas" means docs/examples and generic skill routing exist, not just code extraction

4) Stage migration/compatibility expectations
- Deliverables:
  - define how LeanAtlas remains a first-party host on top of the extracted library
  - define compatibility expectations for existing `tools/loop/**` callers during transition
- Acceptance:
  - later implementation can proceed without breaking current LeanAtlas mainline usage unexpectedly

## TDD / verification plan for later implementation
When implementation starts, add at least:
- contract/doc checks for the reusable-boundary matrix
- packaging/import checks for the extracted library surface
- examples/quickstart checks proving a non-LeanAtlas consumer path exists

Expected verification commands for the implementation wave:
- `uv run --locked python tests/contract/check_loop_contract_docs.py`
- `uv run --locked python tests/contract/check_loop_python_sdk_contract_surface.py`
- `uv run --locked python tests/contract/check_loop_mainline_docs_integration.py`
- `uv run --locked python tests/contract/check_skills_standard_headers.py`
- `uv run --locked python tests/run.py --profile core`

## Decision log
- 2026-03-08: LeanAtlas mainline productization and bounded decoupling are not enough by themselves when the project expects LOOP to become reusable across other Codex projects.
- 2026-03-08: the extraction target is a real reusable Python library with docs/examples, not just a cleaner internal module split.
- 2026-03-08: the extraction target also requires reusable skill routing; code extraction without generic skills would still leave LOOP operationally LeanAtlas-bound.
- 2026-03-08: LeanAtlas remains a first-party host/adaptor, not the definition of LOOP itself.

## Rollback plan
- Remove this child plan and its corresponding master-plan bullet if the project decides not to pursue a reusable standalone LOOP Python library.

## Outcomes & retrospective (fill when done)
- Completed:
  - landed the in-repo reusable `looplib/**` package surface
  - added standalone/non-LeanAtlas entry docs at `docs/setup/LOOP_LIBRARY_QUICKSTART.md`
  - added `examples/looplib_quickstart.py` and routed mainline docs through the standalone entrypoint
- Verification:
  - `uv run --locked python tests/contract/check_loop_library_packaging.py`
  - `uv run --locked python tests/contract/check_loop_mainline_docs_integration.py`
  - `uv run --locked python tests/contract/check_loop_python_sdk_contract_surface.py`
- Residual risks:
  - `looplib` is reusable and documented inside this repository, but it is not yet published as a separate distribution artifact
- Follow-on recommendation:
  - if cross-repo consumption becomes frequent, stage packaging metadata and release mechanics as a separate bounded wave rather than expanding the runtime contract again
