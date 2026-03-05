# LOOP_AUDIT_CONTRACT v0.1 (Wave A)

This contract defines post-hoc audit semantics for LOOP runs.

## 1) AUDIT_FLAGGED semantics

`AUDIT_FLAGGED` means post-hoc audit found risk/defect/non-compliance.

Hard invariants:
- non-blocking for already-finished execution path
- no silent overwrite of original evidence
- mandatory remediation or accepted-risk record

## 2) Required fields for audit-flag events

Each event MUST include:
- `flag_id`
- `run_key`
- `scope` (`NODE` | `RUN` | `GRAPH` | `RESOURCE`)
- `category`
- `severity`
- `confidence` (0..1)
- `summary`
- `evidence_refs`
- `detected_at_utc`

## 3) Severity policy

Severity:
- `S1_CRITICAL`
- `S2_MAJOR`
- `S3_MINOR`

Required consequences:
- `S1_CRITICAL`: immediate incident + promotion freeze + remediation loop
- `S2_MAJOR`: remediation required; promotion blocked until mitigated or accepted risk
- `S3_MINOR`: backlog remediation; no default promotion freeze

## 4) Audit lifecycle

Primary flow:
- `AUDIT_PENDING -> AUDIT_FLAGGED_OPEN -> AUDIT_MITIGATED -> AUDIT_VERIFIED -> AUDIT_CLOSED`

Alternate terminal:
- `AUDIT_ACCEPTED_RISK` (must include explicit rationale + approver + review date)

## 5) Execution relation

- Execution `PASSED` can coexist with audit flag state.
- If `S1_CRITICAL` or unresolved `S2_MAJOR`, quality gate tag is required:
  - `PROMOTION_BLOCKED_BY_AUDIT`
