# LOOP_MCP_CONTRACT v0.1 (Wave A)

This contract defines the third MCP service surface for LOOP orchestration.

## 1) API groups (v1)

The MCP service MUST expose versioned `v1` groups:
- `loop/definitions/*`
- `loop/runs/*`
- `loop/graphs/*`
- `loop/components/*`
- `loop/resources/*`
- `loop/audit/*`
- `loop/providers/*`
- `loop/review-history/*`

## 2) Mutation requirements

Every mutating API call MUST include:
- `idempotency_key`
- `actor_identity`
- `evidence_reference` or `reason`
- `instruction_scope_refs` when the call triggers external/provider agent execution

Provider/review-history requirements:
- `loop/providers/*` endpoints must return deterministic provider-resolution evidence (`provider_id`, resolved command signature, source).
- `loop/review-history/*` endpoints must support append-only reviewer opinion history retrieval for subsequent rounds.

## 3) Error envelope requirements

Responses MUST be deterministic and include:
- stable `error_code` for failures
- `error_class`
- `retryable` boolean

## 4) Compatibility and degradation

MCP is an accelerator, not a single point of failure.

Hard rule:
- if MCP is unavailable, local deterministic runner path must remain usable.

## 5) Versioning

- Path namespace uses `v1`.
- Backward-compatible changes must be minor-safe.
- Breaking changes require version bump.
