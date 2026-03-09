# LOOP Library Quickstart

This page is the quickstart for the reusable in-repo `looplib` surface.

Use it when you want role-neutral LOOP runtime/review/supervisor helpers inside the current LeanAtlas checkout, or when you need the generic entrypoints before touching LeanAtlas-specific workflow adapters.

Generic skill entrypoints:
- `.agents/skills/loop-mainline/SKILL.md`
- `.agents/skills/loop-review-orchestration/SKILL.md`
- `.agents/skills/loop-batch-supervisor/SKILL.md`

LeanAtlas-specific wrappers remain separate:
- `.agents/skills/leanatlas-loop-mainline/SKILL.md`
- `.agents/skills/leanatlas-loop-maintainer-ops/SKILL.md`

## What `looplib` exposes

`looplib` is the reusable import surface for:
- role-neutral graph/runtime helpers
- staged review-orchestration helpers
- batch-supervisor and publication/rematerialization session helpers

Representative imports:

```python
from looplib import (
    LoopGraphRuntime,
    build_default_review_orchestration_bundle,
    execute_batch_supervisor,
    issue_root_supervisor_exception,
    materialize_batch_supervisor,
    publish_capability_event,
)
```

The import surface intentionally stays role-neutral. LeanAtlas host adapters such as git worktree orchestration still live under `tools/loop/**`, not in `looplib`.
`looplib` session helpers are importable without loading the LeanAtlas worktree adapter up front; if a host actually executes a `WORKTREE_PREP` wave, it still needs the host-side git/workflow adapter available at runtime.

## Root supervisor kernel default

For non-trivial reusable LOOP work, the conversation-facing task agent should act as the root supervisor kernel by default:
- materialize the active session/graph before implementation
- publish delegation evidence rather than silently acting as the primary worker
- return integrated closeout authority to the root after child execution

Representative root-supervisor artifacts:
- `graph/root_supervisor_skeleton.json`
- `graph/root_supervisor_delegation.json`
- `graph/root_supervisor_exception.json` when direct/manual fallback is exceptionally required for the active session

Representative root-supervisor helper:
- `issue_root_supervisor_exception(...)`

## Role-neutral in-repo host pattern

For the current in-repo host pattern:
1. import from `looplib`
2. freeze your scope/context artifacts explicitly
3. materialize staged review bundles or batch-supervisor state
4. publish new capability or human-ingress artifacts explicitly
5. rematerialize downstream context instead of relying on hidden chat memory

`looplib` does not require a LeanAtlas `MAINTAINER` or `OPERATOR` workflow for import-time access. Those are LeanAtlas adapters layered on top of the reusable core.
external-repository/non-LeanAtlas packaging is tracked separately by `docs/agents/execplans/20260309_loop_external_repo_split_v0.md`; until that split lands, `looplib` still delegates session/publication helpers to in-repo `tools.loop` implementations.

## Minimal example

See:
- `examples/looplib_quickstart.py`
- `looplib/__init__.py`
- `looplib/runtime.py`
- `looplib/review.py`
- `looplib/session.py`

Example sketch:

```python
from pathlib import Path

from looplib import (
    MaintainerLoopSession,
    build_default_review_orchestration_bundle,
    issue_root_supervisor_exception,
    publish_capability_event,
)

repo_root = Path.cwd()
publish_capability_event(
    repo_root=repo_root,
    publication_id="host.review.default",
    producer_id="host_bootstrap",
    summary="Default staged review execution is available.",
    resource_refs=["docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md"],
)

bundle = build_default_review_orchestration_bundle(
    repo_root=repo_root,
    review_id="host_review",
    scope_paths=["tools/loop/review_orchestration.py"],
    instruction_scope_refs=["AGENTS.md"],
    required_context_refs=["docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md"],
)

session = MaintainerLoopSession.materialize(
    repo_root=repo_root,
    change_id="host_root_supervisor",
    execplan_ref="path/to/frozen_execplan.md",
    scope_paths=["path/to/scoped/file.py"],
    instruction_scope_refs=["AGENTS.md"],
    required_context_refs=["path/to/context.md"],
)

issue_root_supervisor_exception(
    repo_root=repo_root,
    run_key=session.run_key,
    reason_code="TOOLING_BLOCKED",
    blocked_capability="loop.worker.execute",
    evidence_refs=["path/to/context.md"],
    bounded_scope_paths=["path/to/scoped/file.py"],
    fallback_allowed_actions=["DIRECT_MANUAL_EXECUTION"],
    reentry_condition="resume delegated execution after bounded manual repair",
    affected_node_ids=["implement_node"],
)
```

Only use `execution_path="DIRECT_MANUAL_EXCEPTION"` after a real `MaintainerLoopSession.materialize(...)` call has persisted the active session and that same `root_supervisor_exception_ref`. The stable session-issued root exception artifact may append multiple bounded exception entries within one run, but every entry must remain scoped to a proper subset of delegated nodes.

## Relationship to LeanAtlas mainline

For LeanAtlas host usage, start at:
- `docs/agents/LOOP_MAINLINE.md`
- `.agents/skills/leanatlas-loop-mainline/SKILL.md`

For reusable in-repo usage, start at:
- `.agents/skills/loop-mainline/SKILL.md`
