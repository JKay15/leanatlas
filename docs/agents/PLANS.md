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
