# Thread Brief Template (first message for a new GPT thread)

[Workstream ID]:
[Base DocPack]: version=..., content_hash=...

## Objective
One sentence on what this thread will solve.

## Scope
Allowed directories/files (list path prefixes).

## Non-goals
Explicitly state what this thread will not do.

## Inputs (must-read files)
List the contracts/execplans/schemas to load.

## Deliverables
Merge-ready outputs: files, schemas, tests, scenarios, automation entries.

## Output format (required)
Every update must follow the Change Proposal template:
- Summary / Rationale / Files changed / Tests / Risks-Rollback

## Per-reply header (anti-forget)
`[WS-xxx | Base vX.Y | one-line current goal]`
