# Test Coverage Matrix Template (Layer 3 + Layer 4)

Use this template to answer, in one place:

1. Which tests are registered, executed, and passing.
2. Whether non-manifest executable assets have been backfilled into manifest.
3. Whether real-use scenarios completed full-loop validation (validation -> tool deposition -> skills deposition -> on-demand documentation triggering).

## A. Test Execution Matrix

| TestID | Source | In Manifest | Tier | Expected | Actual | Evidence Path | Failure Root Cause | Fix File/Commit | Re-run Passed |
|---|---|---|---|---|---|---|---|---|---|
| T001 | tests/manifest.json | Yes | core | PASS | PASS | artifacts/... | - | - | Yes |
| T002 | e2e golden case | No (to backfill) | core | TRIAGED | TRIAGED | artifacts/... | - | - | Yes |
| T003 | agent_eval scenario | No (to backfill) | nightly | PASS | FAIL | artifacts/... | overlay bridge mismatch | path/to/file | No |

## B. Non-manifest Backfill List

| ItemID | Asset Type | Asset Path | Current Status | Planned Manifest ID | Notes |
|---|---|---|---|---|---|
| N001 | e2e case | tests/e2e/golden/xxx/case.yaml | unregistered | e2e_case_xxx | - |
| N002 | agent_eval scenario | tests/agent_eval/scenarios/xxx/scenario.yaml | unregistered | scenario_xxx | - |
| N003 | agent_eval pack | tests/agent_eval/packs/xxx/pack.yaml | unregistered | pack_xxx | needs task/variant expansion |

## C. Real-Use Loop Closure Matrix (Instructor Task List)

| UseCaseID | Topic | Input Problem/Prompt | Validation Success | Tool Deposition Success | Skills Deposition Success | Correct Doc Target | On-demand Trigger Works | Evidence Path |
|---|---|---|---|---|---|---|---|---|
| U001 | interior point | ... | yes/no | yes/no | yes/no | yes/no | yes/no | artifacts/... |
| U002 | queueing stability | ... | yes/no | yes/no | yes/no | yes/no | yes/no | artifacts/... |
| U003 | empirical process | ... | yes/no | yes/no | yes/no | yes/no | yes/no | artifacts/... |
| U004 | hypothesis testing | ... | yes/no | yes/no | yes/no | yes/no | yes/no | artifacts/... |
| U005 | dynamic pricing | ... | yes/no | yes/no | yes/no | yes/no | yes/no | artifacts/... |
| U006 | BwK (ICML21) | ... | yes/no | yes/no | yes/no | yes/no | yes/no | artifacts/... |

## D. Pass Thresholds

1. `registered_total == executable_total`
2. `executed_total == registered_total`
3. `passed_total == executed_total` OR all failures have closed fix loops
4. Each real-use topic has at least one closed-loop evidence entry
