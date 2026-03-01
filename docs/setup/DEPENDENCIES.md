# Dependencies (External Tools and Libraries)

> This document is the human-readable install/verify index for external dependencies.
> Machine-readable pin source of truth: `tools/deps/pins.json`.
> Any dependency change must update both and pass tests (see `docs/contracts/THIRD_PARTY_DEPENDENCY_CONTRACT.md`).
> First-time onboarding: `docs/setup/QUICKSTART.md`.

---

## 1) Required (all users)

### A) Lean + Lake + mathlib
- Purpose: compile/check pipeline is the system source of truth.
- Version pins:
  - Lean toolchain: `lean-toolchain`
  - mathlib: `require mathlib ... @ "<rev>"` in `lakefile.lean`
- Verification (repo root):
  - `lake --version`
  - `lake build`

### A.1) import-graph (Lake package, optional but recommended)
- Purpose: generate/analyze module import graphs (reused by GC and visualization).
- Version pin: `tools/deps/pins.json` (must stay consistent with `lakefile.lean`).
- Current pinned revision (example, source of truth is still `pins.json`): `v4.28.0`
- Verification:
  - `lake exe graph --help`
- Optional dependency:
  - install Graphviz for image outputs (PDF/PNG), not required for DOT output.

Constraint:
- Lean and mathlib versions must match.

Additional note (important):
- Transitive Lean dependencies must also be reproducible.
- `lakefile.lean` pins direct dependencies; `lake-manifest.json` locks transitive resolution.
- Example: `import-graph` is explicitly required and pinned to a toolchain-compatible revision, and mirrored in `tools/deps/pins.json`.

### B) Python 3 + uv (project Python toolchain)
- Purpose: deterministic gates (schema/contract/tests), e2e/scenario tooling.
- Version pin model (uv standard):
  - Python >= `3.10`
  - Direct deps: `pyproject.toml`
  - Full lock (including transitives): `uv.lock` (generated and maintained by uv; do not edit manually)

Install/sync (recommended):
```bash
uv --version
uv lock --check
uv sync --locked
```

Verification:
```bash
uv run --locked python -c "import importlib.metadata as m; print('jsonschema', m.version('jsonschema')); print('PyYAML', m.version('PyYAML'))"
uv run --locked python -c "import importlib.metadata as m; print('drain3', m.version('drain3'))"
uv run --locked python tests/run.py --profile core
```

Runtime command policy:
- Prefer `./.venv/bin/python ...` after bootstrap has created a healthy local environment.
- Use `uv run --locked python ...` when `.venv` is missing or when you explicitly need lockfile re-resolution.
- If `uv run --locked` fails due network/TLS handshake but `.venv` is already healthy, continue with `./.venv/bin/python ...` and repair network/proxy before forced resync.

Notes:
- If integrating with legacy tools needing `requirements.txt`, export from `uv.lock` when needed, but `requirements.txt` is not the source of truth.

---

## 2) Strongly recommended (for MCP/retrieval/triage acceleration)

### C) lean-lsp-mcp (MCP server)
- Purpose: Lean LSP diagnostics/code-actions/search/verify acceleration for proof loops.
- Version pin: `tools/deps/pins.json` (commit pin by default).
- Install/verify: `docs/setup/external/lean-lsp-mcp.md`

### D) ripgrep (`rg`)
- Purpose:
  - local search backend for `lean-lsp-mcp`
  - deterministic grep fallback when MCP is unavailable
- Install/verify: `docs/setup/external/ripgrep.md`

---

## 3) Optional (phase extensions)

### E) SQLite (MSC2020 MCP / domain dictionary)
- Purpose: local storage/query for MSC2020/LOCAL domain dictionary.
- Note: `lean-domain-mcp` is Repo C in the three-repo topology and is consumed via pinned install/submodule policy; `lean-lsp-mcp` remains external.
- Interface contract: `docs/contracts/MCP_MSC2020_CONTRACT.md`
