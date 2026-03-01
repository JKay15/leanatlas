# REPO_TOPOLOGY_CONTRACT v1

> Goal: freeze LeanAtlas Git boundaries and MCP installation boundaries as auditable rules, and remove ambiguity between local folders and release topology.

---

## 0) Normative conclusions (hard constraints)

- LeanAtlas is governed by **three GitHub repositories** (main repo + skills repo + domain MCP repo).
- The self-developed Domain Ontology MCP is **Repo C**, named `lean-domain-mcp`.
- Third-party `lean-lsp-mcp` is outside the three-repo boundary and installed as an external dependency.
- Repo A/Repo B must not vendor MCP source code; bootstrap installs MCPs from pinned refs.

---

## 1) Three-repo responsibility boundaries

### Repo A (main repo, current workspace)
Purpose: the only entrypoint for LeanAtlas workflows and gates.

Includes:
- `LeanAtlas/**`
- `tools/**`
- `tests/**`
- `docs/**`
- `scripts/**`
- `automations/**`

Forbidden:
- Committing MCP server source code or vendored copies.
- Committing MCP binaries/venvs installed after clone.

### Repo B (skills/KB repo)
Purpose: independent evolution of Codex skills and knowledge accumulation.

Includes:
- `.agents/skills/**`
- `docs/agents/kb/**`

### Repo C (`lean-domain-mcp`)
Purpose: independent versioning for Domain Ontology MCP service implementation and release pins.

Includes:
- Domain MCP server source, packaging, and smoke checks.

Note: research/problem assets may be versioned separately, but they are not part of the three-repo topology contract.

---

## 2) MCP boundaries in Repo A/Repo B (core of this contract)

### 2.1 MCP code must not be vendored into Repo A/Repo B
The following paths are non-compliant if present in main repo:
- `services/lean-domain-mcp/**` (unless it is an explicit pinned submodule pointer to Repo C)
- Any `services/*mcp*` source directory

If such paths exist, they must be marked as temporary development state and removed/moved out before merge.

### 2.2 Installation method
- Install both MCP servers during clone/bootstrap (`lean-domain-mcp` from Repo C + `lean-lsp-mcp` from external source).
- Installation commands, pins, and verification steps must be declared in:
  - `tools/deps/pins.json`
  - `docs/setup/DEPENDENCIES.md`
  - `docs/setup/external/*.md`

### 2.3 Runtime constraints
- Main-repo workflows must support graceful degradation when MCP is unavailable (see `MCP_ADAPTER_CONTRACT.md` / `MCP_LEAN_LSP_MCP_ADAPTER.md`).
- MCP availability must not become a single point of CI failure for the main repo.

---

## 3) Git management rules

- Each repo has independent versioning, PR lifecycle, and rollback.
- A main-repo PR must not include hidden sync of Repo B/Repo C; cross-repo linkage must be explicitly documented with pin relationships.
- External MCP version updates must be done via dependency pin updates, never by committing MCP source code.

---

## 4) Executable acceptance checks (main repo)

Minimum required checks:
- `python tests/contract/check_dependency_pins.py`
- `python tests/contract/check_shared_cache_policy.py`
- `python tests/contract/check_manifest_completeness.py`
- `python tests/run.py --profile core`

---

## 5) Migration notes

When migrating from legacy layout:
1. Freeze main-repo interface contracts and tests first.
2. Then split repos by boundary and establish pin/release process.
3. Finally remove any residual MCP source path from main repo.
