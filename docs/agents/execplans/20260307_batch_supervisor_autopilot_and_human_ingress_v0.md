---
title: Stage batch supervisor/autopilot and human external-input ingress as explicit LOOP completion themes
owner: Codex (local workspace)
status: done
created: 2026-03-07
parent_execplan: docs/agents/execplans/20260307_loop_core_parallel_nested_batch_v0.md
---

## Purpose / Big Picture
The current staged batch roadmap now captures the core/adapters split, but two completion-critical abilities are still too easy to leave implicit: batch-level supervisor/autopilot and bounded human external-input ingress. Without the former, LOOP still depends on a human to hand off from one completed wave to the next. Without the latter, new human information can only arrive through informal chat context rather than through auditable LOOP resources. This plan makes both abilities explicit completion themes so later implementation waves are forced to deliver them instead of treating them as "nice to have."

## Scope
In scope:
- define explicit acceptance for batch supervisor/autopilot
- define explicit acceptance for human external-input ingress plus downstream rematerialization/adoption
- align those themes with existing feedback/maintainer/operator guidance so they are not isolated roadmap text

Out of scope:
- implementing the runtime pieces in this planning wave
- changing passed runtime or review-closeout behavior in this turn

## Interfaces and Files
- `docs/agents/execplans/20260307_loop_core_parallel_nested_batch_v0.md`
- `docs/agents/FEEDBACK_LOOP.md`
- `docs/agents/OPERATOR_WORKFLOW.md`
- `docs/agents/MAINTAINER_WORKFLOW.md`
- `docs/contracts/LOOP_RUNTIME_CONTRACT.md`
- `docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md`
- `docs/contracts/LOOP_PYTHON_SDK_CONTRACT.md`

## Milestones
1) Make the missing end-state explicit
- Deliverables:
  - master batch plan explicitly states that full completion requires both batch autopilot and bounded human-input ingress
- Acceptance:
  - later waves cannot honestly claim "batch complete" while still depending on manual wave-to-wave handoff or hidden chat memory

2) Pin supervisor/autopilot acceptance
- Deliverables:
  - define that a parent loop must be able to:
    - materialize child-wave plans
    - launch and monitor child-wave execution
    - reconcile completed child-wave evidence
    - restart or re-route child waves when policy allows
    - produce final integrated closeout on the latest batch state
- Acceptance:
  - "automatic whole-batch execution" now has concrete success criteria

3) Pin human external-input ingress acceptance
- Deliverables:
  - define that human-provided external information must:
    - arrive through explicit ingress nodes or artifacts
    - be published as append-only evidence
    - trigger explicit context rematerialization before downstream adoption
    - remain citeable/auditable in later node outputs and closeout
- Acceptance:
  - "accept external human information during execution" now has concrete success criteria

## Decision log
- 2026-03-07: a batch is not automatically runnable until a parent-loop supervisor/autopilot exists above the child waves.
- 2026-03-07: human external information is not treated as implicit chat memory; it must be modeled as explicit ingress/publish/rematerialize/adopt flow.

## Rollback plan
- Revert this plan and the corresponding master-plan wording if the scope framing proves wrong.

## Outcomes & retrospective (fill when done)
- Completed:
  - implemented deterministic parent-wave supervision in `tools/loop/batch_supervisor.py`
  - implemented explicit capability publication, bounded human ingress, and context rematerialization in `tools/loop/publication.py`
  - wired LeanAtlas worktree preparation as a host adapter child-wave mode through `tools/loop/worktree_adapter.py`
- Verification:
  - `uv run --locked python tests/contract/check_loop_batch_supervisor.py`
  - `uv run --locked python tests/contract/check_loop_publication_runtime.py`
  - `uv run --locked python tests/contract/check_loop_worktree_adapter.py`
- Residual risks:
  - the committed supervisor is deterministic and bounded, but it is not an unbounded autonomous coding agent; child-wave plans still need explicit materialization and execution policy
- Follow-on recommendation:
  - keep future host-specific child-wave kinds as adapter-layer additions rather than redefining the generic parent-supervisor contract
