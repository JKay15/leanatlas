# Content review template (second level)

Used for item-by-item semantic comparison of intersection files to verify whether v1/v2/v3 feedback issues are covered and determine whether it is really better.

## sheet

| ID | File path | Difference location | Old content summary | New content summary | Override ISSUE_ID | Meet v1/v2/v3 | Is it better | Conclusion | Notes |
|---|---|---|---|---|---|---|---|---|---|
| C001 | path/a | rule_x | Old rule behavior | New rule behavior | ISSUE-001 | YES | YES | PASS | - |
| C002 | path/b | section_y | Missing constraint | New constraint | ISSUE-014 | Yes | Yes | Pass | - |
| C003 | path/c | function_z | Working but fragile | More stable but more expensive | ISSUE-021 | Yes | Pending | To be modified | Need to supplement performance data |

## Judgment criteria

### Meet v1/v2/v3

- `Yes`: The corresponding question has been covered and there is an evidence path.
- `No`: Not covered or covered incompletely.

### Is it better?

- `Yes`: verifiable improvement, meeting at least one of the following.
- More testable
- More observable
- less ambiguity
- Clearer fault boundaries
- `No`: Regress or introduce new risks.
- `To be determined`: lack of evidence, need to supplement experiments.

### in conclusion

- `Pass`
- `Reject`
- `To be modified`

## Audit rules

1. Intersecting documents must be reviewed item by item, and "passing the entire document with one vote" is not allowed.
2. Each difference must be bound to ISSUE_ID, or the source of "new value" must be given.
3. If the conclusion is `passed`, it must be mapped to the test verification item.
4. If the conclusion is `Rejected/To be modified`, the action items and person in charge must be given.

## Output requirements

1. Summary: `Passed/Rejected/Pending Modification` quantity.
2. List all uncovered ISSUE_IDs.
3. Provide a list of "items that must be changed".
