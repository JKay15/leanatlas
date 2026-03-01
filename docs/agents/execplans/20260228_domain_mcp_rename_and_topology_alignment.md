# ExecPlan: Domain MCP Rename and Topology Alignment

Date: 2026-02-28  
Mode: MAINTAINER  
Owner: Codex (local workspace)

## 1) Scope

This plan performs one bounded rename/alignment change:

1. Rename the legacy Domain MCP tools directory to `tools/lean_domain_mcp/**`.
2. Update all in-repo references from old path tokens to the new path.
3. Keep MSC2020 terminology for data taxonomy (only rename MCP service identity).
4. Verify contracts/schemas/navigation and core test tier.

## 2) Glossary

- `lean-domain-mcp`: self-developed Domain Ontology MCP service identity.
- `lean_domain_mcp`: snake_case token used in schema/docs fields.
- `MSC2020`: domain taxonomy standard; not renamed.

## 3) Files to change

- Move directory:
  - `<legacy_domain_mcp_tools_dir>/**` -> `tools/lean_domain_mcp/**`
- Update references in:
  - `scripts/**`
  - `docs/**`
  - `tools/**`
  - `tests/**`
  - `.agents/skills/**`
- Regenerated docs:
  - `docs/navigation/FILE_INDEX.md`

## 4) Milestones

### M1: Move source directory

Commands:

```bash
# Applied in this plan:
test -d <legacy_domain_mcp_tools_dir>
mv <legacy_domain_mcp_tools_dir> tools/lean_domain_mcp
```

Acceptance:
- New path exists; old path removed.

### M2: Rewrite references

Commands:

```bash
rg -n "<legacy_domain_mcp_tokens>" <target_roots_before>
rg -n "tools/lean_domain_mcp|tools\\.lean_domain_mcp|lean_domain_mcp|services/lean-domain-mcp" <target_roots_after>
```

Acceptance:
- No old tokens remain in tracked docs/scripts/tests/tools/skills.

### M3: Regenerate indexes and verify

Commands:

```bash
./.venv/bin/python tools/docs/generate_file_index.py --write
./.venv/bin/python tests/schema/validate_schemas.py
./.venv/bin/python tests/contract/check_setup_docs.py
./.venv/bin/python tests/contract/check_dependency_pins.py
./.venv/bin/python tests/contract/check_doc_pack_completeness.py
./.venv/bin/python tests/contract/check_file_index_reachability.py
./.venv/bin/python tests/contract/check_english_only_policy.py
./.venv/bin/python tests/run.py --profile core
```

Acceptance:
- All listed checks pass.

## 5) Rollback points

- Directory rename rollback:
  - `tools/lean_domain_mcp/**` back to `<legacy_domain_mcp_tools_dir>/**`
- Reference rollback:
  - revert only rename tokens (`lean_domain_mcp`/`lean-domain-mcp`) in touched files.
- Full rollback:
  - revert this plan’s changed files as one slice to avoid partial path drift.
