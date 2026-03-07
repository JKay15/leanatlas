# ExecPlans (execution plan standard)

If any of the following is true, you must write an ExecPlan **before** changing code:
- you need to modify `LeanAtlas/**`, `tools/**`, `docs/contracts/**`, the test framework, or any cross-directory structure
- you need to add/change schemas, workflow contracts, or gate logic
- you need to introduce a new external dependency or a new MCP service
- the task is expected to take >30 minutes, touches multiple files, or contains obvious unknowns

## Goal
An ExecPlan should be sufficient for someone unfamiliar with the repo to reproduce your work and verify results using only:
- the ExecPlan,
- the current working tree.

## Non-negotiable requirements
1) **Self-contained**: define terms; list which files change, why, and how to verify.
2) **Acceptable**: every milestone includes runnable commands + expected outputs.
3) **Replayable**: decision changes during the work must be recorded so others can reproduce.
4) **TDD first**: write/update tests first, then implement, then update docs.
5) **Clean artifacts**: do not commit temporary logs/artifacts; update `.gitignore` and cleaning scripts when needed.

## Maintainer LOOP rule
For non-trivial maintainer work on system surfaces, the plan is not the whole process. non-trivial maintainer work MUST materialize a maintainer LOOP graph and close through that graph.

Required sequence:
- `ExecPlan -> graph_spec -> test node -> implement node -> verify node -> AI review node -> LOOP closeout`

Implications:
- `ExecPlan` freezes scope and acceptance before code changes.
- maintainer session materialization must happen before implementation begins; observers should be able to see `GraphSpec.json` plus append-only maintainer session/node-journal artifacts even before closeout.
- preferred maintainer path: use the Python maintainer facade (`MaintainerLoopSession` or an equivalent canonical helper), not a post-hoc summary-only flow.
- `test node` must exist before `implement node`; TDD still applies.
- when an ExecPlan needs to cite settled-state maintainer closeout in its own `Outcomes & retrospective`, it must use the stable execplan-addressable closeout alias (`artifacts/loop_runtime/by_execplan/<stable_execplan_id>/MaintainerCloseoutRef.json`)
- an ExecPlan must not cite a run-key-specific `GraphSummary.jsonl` path inside its own body for settled-state closeout, because doing so perturbs the plan's own `execplan_hash`
- maintainer closeout must happen while the frozen ExecPlan and other frozen inputs still match the materialized session; stale execplan bytes are not allowed to rewrite the stable closeout alias.
- if multiple maintainer sessions exist for the same `execplan_ref`, the stable closeout alias must stay pinned to the newest authoritative session rather than being overwritten by an older same-plan session that closes later.
- once `ai_review_node` is recorded, maintainer closeout must also preserve the reviewed scope itself; mutate-and-restore scope drift after `ai_review_node` must be rejected using reviewed-scope evidence such as `scope_fingerprint` / `scope_observed_stamp`.
- routine `manual closeout` is not an ordinary maintainer path; it is an exception path only.

## Where ExecPlans live
- New plans: `docs/agents/execplans/<YYYYMMDD>_<short_name>.md`
- One plan solves one thing; split large tasks into multiple plans.

## Minimal ExecPlan template (copy/paste)

---
title: <one-line summary>
owner: <human owner / team>
status: draft|active|done
created: <YYYY-MM-DD>
---

## Purpose / Big Picture
Explain in 3–8 sentences: why this matters, what pain it fixes, and what the user can do afterwards.

## Glossary
Define key terms introduced or relied upon by this plan.

## Scope
State what is in-scope and out-of-scope. Be explicit about:
- which directories are allowed to change
- which directories are forbidden
- whether schemas/contracts change

## Interfaces and Files
List required files (exact paths) and their roles.
If needed, include function signatures, schema snippets, or CLI commands.

## Milestones
Write 2–6 milestones in order. Each milestone must include:
- deliverables (which files change)
- commands (how to run)
- acceptance (what output counts as success)

## Testing plan (TDD)
Be explicit about:
- which new tests are added (paths)
- which failure/regression scenarios are covered
- how contamination is avoided (test-only injection must be via workspace overlays)

## Decision log
Record major design choices and why alternatives were rejected.

## Rollback plan
If problems appear after merging, how to roll back (which files, and how to verify rollback).

## Outcomes & retrospective (fill when done)
What was achieved, surprises, and next recommendations.
