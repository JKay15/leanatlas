# LOOP_RESOURCE_ARBITER_CONTRACT v0.1 (Wave A)

This contract defines shared-resource writes for LOOP execution.

## 1) Resource classes

`resource_class` MUST be one of:
- `IMMUTABLE`
- `APPEND_ONLY`
- `MUTABLE_CONTROLLED`

Rules:
- `IMMUTABLE`: read-only.
- `APPEND_ONLY`: only append operations are allowed.
- `MUTABLE_CONTROLLED`: lease + CAS protocol is mandatory.

## 2) Lease and CAS protocol (required)

For `MUTABLE_CONTROLLED`, writes MUST follow:
1. Acquire lease (`lease_id`, `owner`, `expires_at_utc`).
2. Read base snapshot/hash.
3. Attempt CAS commit.
4. On CAS conflict, write conflict record and retry/escalate.
5. Release lease.

## 3) Journal requirements

Each successful mutable commit MUST append journal evidence with:
- `resource_id`
- `lease_id`
- `actor`
- `old_hash`
- `new_hash`
- `reason/evidence`
- `committed_at_utc`

## 4) Conflict handling

Conflict events MUST be append-only and include:
- conflict type (`LEASE_CONFLICT` or `CAS_CONFLICT`)
- conflicting actor(s)
- snapshot/hash info
- retry or escalation decision

## 5) Compatibility requirement

Resource arbitration semantics must be identical for:
- local runner path
- MCP orchestration path
