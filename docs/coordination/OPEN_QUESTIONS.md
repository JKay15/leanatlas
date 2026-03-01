# Open Questions (for parallel execution)

- Q-0001: Upgrade GC use signals from reachability approximation to real uses_value/uses_type telemetry.
  - Owner: PHASE-3 (or WS-GC)
  - Status: open
  - Needed input: final AttemptLog/telemetry schema; seed_id <-> declaration ownership mapping
  - Done when: `GCPlan.last_used_clock` is generated from real usage events and revival triggers are usage-based

- Q-0002: GC import-edge performance cache strategy (chunking + cache keys).
  - Owner: PHASE-3 (or WS-GC)
  - Status: open
  - Needed input: repo-size baseline; allowed cache directories and cleanup policy
  - Done when: no O(N^2) degradation across repeated propose/apply in soak scenarios

- Q-0003: Thresholds for upgrading PromotionGate structural signals from WARN to FAIL.
  - Owner: PHASE-3 (or WS-PROMOTION)
  - Status: open
  - Needed input: benchmark baselines; import-structure statistics from real projects
  - Done when: hard gates vs report-only signals are explicitly defined

- Q-0004: Final shape for DedupGate allowlist/annotation of legitimate duplicates.
  - Owner: PHASE-3 (or WS-DEDUP)
  - Status: open
  - Needed input: mathlib duplicate-linter details; feasibility of Lean attribute approach
  - Done when: false positives are controlled and auditable; key edge cases are covered in nightly tests

- Q-0005: MSC2020 MCP data versioning and overlay merge strategy.
  - Owner: PHASE-MCP-DOMAIN
  - Status: open
  - Needed input: data source/license/update cadence; conflict resolution rules
  - Done when: versions are pin-able, incrementally updatable, and diff-queryable by clients

- Q-0006: PromotionGate evidence package persistence and artifact-size control.
  - Owner: PHASE-3 (or WS-PROMOTION)
  - Status: open
  - Needed input: CI artifact retention policy and size cap; what evidence can be committed (default: no)
  - Done when: evidence path/naming/sha256 rules are fixed and soak artifact growth is bounded

- Q-0007: How to organize and version representative Phase6 oracle sets.
  - Owner: PHASE-6
  - Status: open
  - Needed input:
    - Oracle storage/versioning model (default external path: `~/.cache/leanatlas/oracle/<id>/`), plus team sync method
    - Prompt-script policy: one-shot correct hints vs staged wrong->fix loops
    - Per-problem required prelabels: minimal assumptions, expected mathlib/Toolbox tools, tool deposition targets, expected KB/skill tags
  - Done when: oracle packs are reproducible, shareable, and evaluation semantics are stable across runs
