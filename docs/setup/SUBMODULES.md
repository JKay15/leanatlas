# Submodules and Split Topology

LeanAtlas can run as a single bundled repo, but the recommended release topology is split:

- Repo A: `leanatlas` (main workflow repo)
- Repo B: `leanatlas-skills` (mounted at `.agents/skills/`)
- Repo C: `lean-domain-mcp` (self-developed Domain Ontology MCP repository)

This page defines the Git-side setup rules.

## 0) Clone and initialize

When using submodules:

```bash
git clone --recurse-submodules <REPO_A_URL>
```

If you already cloned without submodules:

```bash
git submodule update --init --recursive
```

## 1) Canonical mount points

Repo A expects:

- Skills repo (Repo B): `.agents/skills/` (git submodule)
- Domain MCP repo (Repo C): installed during bootstrap from pinned ref; optional debug mountpoint `services/lean-domain-mcp/` as a pinned submodule.

Current Repo B submodule source:
- URL: `https://github.com/JKay15/leanatlas-skills.git`
- Commit pin (from Repo A gitlink): `c6278464589f32fb1b5d9d4dd5ed42839982b4e4`

Local Codex Home skills (for example under `$CODEX_HOME/skills` or `~/.codex/skills`) are machine-local tools and must not be committed to Repo A.

Hard rule:

- Do not remount Repo B at a different path.

## 2) MCP boundary (non-negotiable)

For Repo A/Repo B:

- Domain MCP source is not vendored; it is managed by Repo C (`lean-domain-mcp`) and consumed via pinned install/submodule policy.
- Third-party `lean-lsp-mcp` is external install during bootstrap.

Do not commit MCP source or vendored MCP binaries into Repo A.

Reference contracts:

- `docs/contracts/REPO_TOPOLOGY_CONTRACT.md`
- `docs/contracts/MCP_ADAPTER_CONTRACT.md`
- `docs/contracts/MCP_LEAN_LSP_MCP_ADAPTER.md`

## 3) Updating submodule pins

Example update flow:

```bash
cd .agents/skills && git fetch && git checkout <NEW_COMMIT>
cd ../.. && git status
```

Inspect pinned submodule commit from Repo A root:

```bash
git submodule status .agents/skills
```

Then verify from Repo A root:

```bash
./.venv/bin/python tests/run.py --profile core
```

If external dependencies are available:

```bash
./.venv/bin/python tests/run.py --profile nightly
```

## 4) Operational notes

- Keep `AGENTS.override.md` local only (gitignored).
- Cross-repo updates must be explicit in PR descriptions (which repo changed and which pin was bumped).
