# File Mapping Template (Layer 1)

Use this template to build a one-to-one mapping between current repository files and refactored target files, with explicit keep/delete/add/move/split/merge decisions.

## Table

| ID | Current Path | Target Path | Relation Type | Decision | Why Needed | Risk | Evidence / Linked ISSUE_ID |
|---|---|---|---|---|---|---|---|
| F001 | path/a | path/a | overlap | keep | preserve compatibility | low | ISSUE-001 |
| F002 | path/b | - | delete | pending review | replaced by path/c | medium | ISSUE-014 |
| F003 | - | path/c | add | pending review | add gate capability | medium | ISSUE-021 |
| F004 | path/d | path/e | move/rename | pending review | unify directory structure | medium | ISSUE-030 |
| F005 | path/f | path/f1 + path/f2 | split | pending review | reduce coupling | medium | ISSUE-042 |
| F006 | path/g + path/h | path/gh | merge | pending review | reduce duplicated implementations | high | ISSUE-055 |

## Enums

### Relation Type

- `overlap`
- `delete`
- `add`
- `move/rename`
- `split`
- `merge`

### Decision

- `keep`
- `delete`
- `add`
- `modify`
- `pending review`

## Review rules

1. Every delete item must include replacement mapping or explicit deprecation statement.
2. Every add item must bind to issue source (ISSUE_ID) and acceptance criteria.
3. Every move/rename item must include impacted references and migration plan.
4. No unclassified files are allowed.

## Output requirements

1. Summary counts: `total / overlap / delete / add / move / split / merge`.
2. List all high-risk items (risk=high) with rollback plans.
