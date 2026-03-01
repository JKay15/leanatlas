# MCP_LEAN_LSP_MCP_ADAPTER

Goal: integrate `lean-lsp-mcp` (an external dependency) into LeanAtlas in an **auditable + downgradeable** way.
Install and local verification: `docs/setup/external/lean-lsp-mcp.md`.

## 0) Terms and positioning

- **MCP (Model Context Protocol)**: a tool-call protocol used by agents.
- **lean-lsp-mcp**: an external MCP server that exposes Lean LSP capabilities as tools.
- **Adapter**: LeanAtlas’s capability abstraction layer. Tool names can change underneath; capability semantics and logging must not.

Hard rules:
- External retrieval only proposes candidates; final truth is local `lake build` + env validation.
- MCP is an accelerator: it may be absent; there must be a downgrade path.
- Every MCP call must be recorded in AttemptLog (auditable).

## 1) Minimal capability set (required)

The adapter must expose these capabilities. Underlying MCP tool names may differ, but capabilities must exist.

### A) Diagnostics
- Input: file path (Proof/Cache/Scratch)
- Output: structured diagnostics (file, range, severity, message)
- Used to populate `RunReport.diagnostics`

### B) Code actions
- Input: file path + range
- Output: apply-able edits + explanation
- Used for fast suggestions (`simp?`, `exact?`, `aesop?`, etc.)

### C) Local search
- Input: query (string/regex)
- Output: candidate locations (file/line)
- Used in the retrieval ladder as the highest-reliability local recall

### D) Verify
- Output: unsafe/axioms/`sorryAx` detection (or equivalent)
- Used for SUCCESS sanity checks

## 2) Timeouts and budgets (required)

- Every MCP call must have a hard timeout.
- Multi-attempt loops must have a total budget (tactic budget, wall-time budget).
- AttemptLog must record per call:
  - tool name
  - input summary (not full payload when large)
  - start/end timestamps
  - status (OK/ERROR/TIMEOUT)
  - error summary

## 3) Downgrade strategy (required)

When MCP is unavailable, times out, or returns an unparseable response:

- diagnostics: downgrade to parsing `lake build` output
- code actions: treat as unavailable; use small deterministic edits + rebuild
- local search: downgrade to repo grep (prefer `rg`, otherwise Python fallback)
- verify: at minimum run `lake build` and scan for `sorry`/axioms using a local script

Downgrade principles:
- The small loop must not deadlock: it must continue attempts or exit TRIAGED (`TOOLING_FAILURE`).
- Downgrade must be auditable: AttemptLog must set `tooling_failed=true` and `fallback_used=true`.

## 4) Versioning and reproducibility (required)

Every run must record:
- MCP server identity (version/commit if available)
- tool list hash (if server can provide it)

If version drift changes behavior, reports must make the drift visible.

## 5) TDD (required)

- Without MCP installed, OPERATOR must still complete the small loop and exit (at least TRIAGED).
- Nightly healthcheck must produce a machine-readable report (even if status is UNKNOWN).
