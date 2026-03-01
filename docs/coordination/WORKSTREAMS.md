# Parallel Workstreams (Recommended Split)

> Note: `WS-DEDUP/WS-PROMOTION/WS-GC` are optional parallel substreams inside **Phase3 (Library Growth Loop)**.
> These splits are recommended, not mandatory. Every thread must pick one ID and respect scope.

## WS-DEDUP
- Scope: `docs/contracts/*DEDUP*`, `docs/agents/execplans/phase3_dedup_*`, `docs/schemas/Dedup*`, `tools/dedup/**`, `tests/**dedup**`
- Deliverables:
  - Reuse mature duplicate-declaration linter strategy (no reinvention)
  - Improve DedupReport evidence fields (`module/alias/allowlist`)
  - At least one nightly scenario: inject duplicate instance -> gate fail

## WS-PROMOTION
- Scope: `docs/contracts/*PROMOTION*`, `docs/agents/execplans/phase3_promotion_*`, `docs/schemas/Promotion*`, `tools/promote/**`, `tests/**promotion**`
- Deliverables:
  - Rule-of-Three threshold + structured exception path
  - Structural signals integration (`import-graph`, `min_imports`, `directoryDependency`, `upstreamableDecl`)
  - Compat/deprecation rules (declaration/module)
  - At least one sequence scenario: reuse -> promote -> regression -> fix

## WS-GC
- Scope: `docs/contracts/*GC*`, `docs/agents/execplans/phase3_gc_*`, `docs/schemas/GC*`, `tools/gc/**`, `tools/index/gc_state.json`, `tests/**gc**`
- Deliverables:
  - roots + reachability pipeline (prefer `import-graph` reuse)
  - Link `gc_state` source of truth with retrieval strategy
  - Revival proposal generation for quarantined/archived hits (explicit and auditable)
  - At least one soak scenario: quarantine -> reuse -> revive -> promote

## WS-MCP
- Scope: `docs/contracts/MCP_*`, `docs/setup/external/*mcp*`, `tools/mcp/**`, `tools/lean_domain_mcp/**`, `tests/**mcp**`
- Deliverables:
  - lean-lsp-mcp integration contract (degradation, timeout, audit)
  - MSC2020 MCP with overlay/versioning strategy
  - Dependency pin + smoke (`uv/uvx`, `rg`)

## WS-AUTOMATION
- Scope: `automations/**`, `docs/contracts/AUTOMATION*`, `tests/automation/**`, `tools/deps/**`, `docs/testing/**`
- Deliverables:
  - all automations must have registry entries + dry-run TDD
  - nightly/weekly audit tasks (docpack completeness + pins + memory coverage)
  - explicit worktree/isolation policy

## Suggested skill ownership inside Phase3

- WS-DEDUP: `.agents/skills/leanatlas-dedup/`
- WS-PROMOTION: `.agents/skills/leanatlas-promote/`
- WS-GC: `.agents/skills/leanatlas-gc/`

This is a recommendation for Phase3 internal parallelism; top-level coordination still uses Phase3/4/5/M.
