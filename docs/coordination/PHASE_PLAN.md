# Top-Level Phase Plan (Aligned with Contracts and Project Memory)

> Goal: keep top-level phase semantics stable during parallel development, and explicitly assign cross-cutting ownership for skills/automation.
> Convention: **Dedup / Promotion / GC all belong to Phase3 (Library Growth Loop).**
> Parallel execution may split Phase3 into workstreams (`WS-DEDUP/WS-PROMOTION/WS-GC`) without changing top-level phase numbering.

## Baseline (must match)

- Base DocPack: `DOC_PACK_ID.json` at repo root
- Every parallel thread must restate in its first message:
  - `doc_pack_version`
  - `content_hash_sha256`
- All changes must satisfy:
  - `docs/coordination/USER_REQUIREMENTS.md`
  - `docs/coordination/PARALLEL_PROTOCOL.md`

## Top-level phases (authoritative)

### Phase1: Proof Loop & Triage (Codex in the loop)

- Goal: run the path "natural language problem -> Lean proof -> SUCCESS/TRIAGED" with reproducible triage semantics.
- Core artifacts: RunReport / AttemptLog / RetrievalTrace, with deterministic SUCCESS/TRIAGED criteria.

### Phase2: Testing Harness (real workflow tests + sequence + stress)

- Goal: build testing as engineering guardrail (`core/nightly/soak`) including sequence and pressure scenarios.
- Core artifacts: registry-based test matrix (`tests/manifest.json`) + scenario runner + cleanup policy.

### Phase3: Library Growth Loop (Dedup + Promotion + GC)

- Goal: complete the dedup/promotion/gc loop with full auditability, rollbackability, and reproducibility.
- Submodules (still Phase3): DedupGate, PromotionGate, GCGate.

### Phase4: Domain / MCP Integration

- Goal: integrate lean-lsp-mcp, MSC2020 MCP, and domain-driven retrieval ladder with versioned dictionaries and degradation strategy.

### Phase5: Platform (Automation + Bench/Evals + Skills Regen)

- Goal: provide platform capabilities, not business-semantic guesswork:
  - automation registry + dry-run TDD
  - bench/eval regression loop
  - deterministic skills regeneration framework

### PhaseM: Merge/Release

- Goal: integrate phase outputs into a new base DocPack, resolve conflicts, keep tests green, update decision logs.

## Cross-cutting ownership for skills/automation

Principle:
- The phase defining an interface owns corresponding business semantics.
- Phase5 owns platform framework and deterministic regeneration only.

### Rule 1: Capability manifests

- Each top-level phase (3/4/5) maintains `tools/capabilities/phase<N>.yaml`.
- Manifest includes: CLI commands, input/output artifacts, key schemas, external dependency pins, minimal smoke checks.

### Rule 2: Skill directory ownership

Default ownership:
- Phase3: `.agents/skills/leanatlas-dedup/`, `.agents/skills/leanatlas-promote/`, `.agents/skills/leanatlas-gc/`
- Phase4: `.agents/skills/leanatlas-domain-mcp/`
- Phase5: `.agents/skills/leanatlas-automations/` and skills-regen framework docs
- PhaseM: merge only, no new business skills

For skills spanning multiple phases, use RFC to avoid overwrite races.

## Parallel recommendation

- Strict "one phase per GPT Pro" mode: run four threads (`Phase3/Phase4/Phase5/PhaseM`).
- If Phase3 needs finer parallelism, use `WS-DEDUP/WS-PROMOTION/WS-GC` under the same top-level phase.
