# Domain Ontology MCP (Install and Verify)

> This page answers two things only:
> 1) how to run LeanAtlas Domain Ontology MCP locally (stdio)
> 2) how to verify it exposes `domain/*` tools
>
> Contract: `docs/contracts/MCP_MSC2020_CONTRACT.md`.

---

## 0) What it is for in LeanAtlas

Domain Ontology MCP is the source of truth for domain routing and domain taxonomy alignment.

Main roles:
- Domain selection: map prompt/problem semantics to MSC2020 (or explicitly approved local domains)
- Domain expansion: expand from fine code to ancestors/subtrees/siblings for retrieval `DOMAIN_EXPAND`
- Pruned root suggestions: map domain to repo subdirectories when overlay provides mappings

It is read-only and does not replace `lake build`.

---

## 1) Install

Domain MCP (`lean-domain-mcp`) is managed as Repo C in the three-repo topology.
From Repo A usage perspective, it is installed during clone/bootstrap from a pinned ref and is not vendored into Repo A.

You need:
- Python >= 3.10 (see `tools/deps/pins.json`)
- External source configured (`LEANATLAS_DOMAIN_MCP_UVX_FROM` recommended)
- Run bootstrap

Example:

```bash
export LEANATLAS_DOMAIN_MCP_UVX_FROM='git+https://github.com/ORG/DOMAIN_MCP_REPO@COMMIT_SHA'
bash scripts/bootstrap.sh
```

---

## 2) Verify (minimal smoke)

Preferred external command check (command can be overridden by `LEANATLAS_DOMAIN_MCP_COMMAND`, default `domain-mcp`):

```bash
domain-mcp --smoke
```

During migration, if only repo-local dev server exists, temporary fallback is:

```bash
python tools/lean_domain_mcp/domain_mcp_server.py --msc2020-mini --smoke
```

Expected result: exit code 0 with health output.

---

## 3) Start MCP server (stdio)

### 3.1 Built-in mini taxonomy (dev/test)

```bash
domain-mcp --msc2020-mini
```

### 3.2 Full bundle after ingest (recommended)

First generate bundle via `docs/setup/external/msc2020.md`, then run:

```bash
domain-mcp --bundle .cache/leanatlas/msc/msc2020.bundle.json
```

With overlay mappings:

```bash
domain-mcp \
  --bundle .cache/leanatlas/msc/msc2020.bundle.json \
  --overlay tools/lean_domain_mcp/data/domain_overlay_example.json
```

---

## 4) Degradation requirements (must still run without MCP)

If Domain MCP is unavailable or taxonomy data is missing:
- domain routing must degrade to `UNKNOWN` (or structure-only fallback)
- retrieval pruning must degrade to no-prune (full `repo_root`)

This is mandatory under `docs/contracts/MCP_ADAPTER_CONTRACT.md`.
