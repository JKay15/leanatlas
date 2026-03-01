---
name: leanatlas-maintainer-execplan
description: Use this skill in MAINTAINER mode to create a self-contained ExecPlan for a non-trivial system change, then implement it with TDD.
---

## Use when
- You are in **MAINTAINER** mode and the change is non-trivial (new phase/module/gate/contract/test), so you need an ExecPlan first.
- You must implement with TDD and keep the change auditable and mergeable.

## Don't use when
- You are proving a single problem in OPERATOR mode (use `leanatlas-operator-proof-loop`).
- You are doing a tiny doc-only typo fix that does not justify an ExecPlan.

## Outputs
- `docs/agents/execplans/<YYYYMMDD>_<short_name>.md` (self-contained)
- Minimal patch implementing milestones + passing tests

## Must-run checks
- `uv run --locked python tests/run.py --profile core`
- `lake build`

## Preconditions
- MAINTAINER mode is active (root `AGENTS.override.md` exists and is not committed).

## Steps
1) Read `docs/agents/PLANS.md`.
2) Create a new plan under `docs/agents/execplans/<YYYYMMDD>_<short_name>.md`.
3) Fill the plan until it is self-contained:
   - define terms
   - list exact files to edit
   - list commands and acceptance outputs
4) Implement milestone-by-milestone:
   - write/adjust tests first
   - implement
   - update docs/contracts/schemas as needed
5) Verify:
   - `python tests/run.py --profile core`
   - relevant e2e/scenario tests
6) Ensure repo is clean:
   - no artifacts/logs committed
   - `git status --porcelain` must be empty

