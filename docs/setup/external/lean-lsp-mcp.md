# lean-lsp-mcp (Install and Verify)

> This page answers one question only: how to install and verify `lean-lsp-mcp` locally.
> Adapter semantics and degradation policy: `docs/contracts/MCP_LEAN_LSP_MCP_ADAPTER.md`.
>
> Important: LeanAtlas uses **pinned versions** (exact commit/version), not drifting sources like `@latest`.
> Pin source of truth: `tools/deps/pins.json`.

---

## 0) What it is for in LeanAtlas

`lean-lsp-mcp` is the LSP executor/accelerator for proof loops. Typical capabilities:
- diagnostics
- code actions (`simp?`, `exact?`, etc.)
- local search
- verify/sanity checks

It is not the final source of truth. `lake build` remains authoritative.

---

## 1) Install uv (pinned version recommended)

`uvx` is an alias of `uv tool run`, which runs tools in isolated environments.

### 1.1 macOS/Linux
```bash
curl -LsSf https://astral.sh/uv/0.10.4/install.sh | sh
```

### 1.2 Windows PowerShell
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/0.10.4/install.ps1 | iex"
```

### 1.3 Verify
```bash
uv --version
uvx --version
```

---

## 2) Repo prerequisite

Build once at repo root before first MCP run:

```bash
lake build
```

Reason: avoid first-run compile spikes causing MCP startup timeouts.

---

## 3) Run pinned `lean-lsp-mcp`

LeanAtlas pin:
- tag: `v0.22.0`
- commit: `5969dba51ec7c602fb861474fbe01bc166d81734`

### 3.1 Minimal startup check
```bash
uvx --from git+https://github.com/oOo0oOo/lean-lsp-mcp@5969dba51ec7c602fb861474fbe01bc166d81734 lean-lsp-mcp --help
```

### 3.2 Start MCP server (stdio)
```bash
uvx --from git+https://github.com/oOo0oOo/lean-lsp-mcp@5969dba51ec7c602fb861474fbe01bc166d81734 lean-lsp-mcp
```

Use commit pin to keep reproducibility even when upstream releases change.

---

## 4) Client config shape (example)

Different clients use different formats, but args should keep pinned source explicit.

```json
{
  "command": "uvx",
  "args": [
    "--from",
    "git+https://github.com/oOo0oOo/lean-lsp-mcp@5969dba51ec7c602fb861474fbe01bc166d81734",
    "lean-lsp-mcp"
  ]
}
```

---

## 5) Workflow-level validation

Run MCP healthcheck (current probe is lightweight but output path is stable):

```bash
python tools/mcp/healthcheck.py --out artifacts/mcp_health/latest.json
cat artifacts/mcp_health/latest.json
```

Future phases can strengthen this to real MCP tool invocations with degradation hints.

---

## 6) Common pitfalls

- Skipping `lake build`: first MCP run may timeout while compiling.
- Missing `rg`: local search and grep fallback become slow/failing (see `docs/setup/external/ripgrep.md`).
