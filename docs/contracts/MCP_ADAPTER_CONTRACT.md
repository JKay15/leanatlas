# MCP_ADAPTER_CONTRACT

Purpose: integrate MCP (Model Context Protocol) into LeanAtlas **without breaking determinism or reliability**.

LeanAtlas may use MCP for retrieval/triage/build acceleration, but must satisfy:
- The only authority is the **local Lean environment** (post `lake build`).
- If MCP is unavailable, the system must still exit cleanly as **SUCCESS** or **TRIAGED**.

---

## 1) Role of MCP in LeanAtlas

MCP is allowed to act as:
- candidate recall and “fast confirmation” in the retrieval ladder (local search, declaration location, hover/type)
- build/triage assistance (diagnostics, code actions)
- safety checks (verify: forbid `sorryAx` / unsafe options)

MCP is not allowed to act as:
- an authoritative prover (any conclusion must be verified by local compilation/validation)
- the only retrieval source (official retrieval is environment-based; MCP only accelerates locating candidates)

---

## 2) Mandatory downgrade path

Every MCP call must have a downgrade path.

If MCP is unavailable / times out / returns an error:
- the retrieval ladder must continue (Toolbox → Seeds → mathlib)
- the Attempt stage must be able to obtain diagnostics at least via `lake build`
- the Decide stage must be able to enter TRIAGED (`tooling_failure`) and output evidence

Conclusion: MCP can only improve speed; it must not be a single point of failure.

---

## 3) Observability and audit (aligned with Phase1)

All MCP calls must be recorded in AttemptLog:
- `tool_name`
- `request_fingerprint` (may be a hash)
- `status` (`OK` / `TIMEOUT` / `ERROR`)
- `latency_ms`

All MCP results must be traceable into:
- `RetrievalTrace.steps[]` (retrieval-related)
- `RunReport.diagnostics` (diagnostics-related)

---

## 4) Safety and permissions

- An MCP server may have filesystem access.
- Default policy is **read-only**; any writes must be explicitly approved in MAINTAINER mode and recorded.
- Any tool that executes external commands or performs network access is high risk and requires explicit approval.

---

## 5) Versioning and compatibility

The adapter layer must record:
- `server_name` / `server_version`
- `tool_list_hash`
- key configuration (transport, timeout, root_path)

If a server upgrade changes tool lists or behavior, it must be detected first via nightly healthcheck before we rely on it.
