# tools/bench

This directory contains **deterministic aggregations and statistics** over run artifacts (no LLM).

- `collect_telemetry.py`
  - normalizes run artifact inputs from multiple roots into `artifacts/telemetry/**`
  - writes `artifacts/telemetry/index.json` for auditable source->dest mapping
  - keeps telemetry-dependent automations reproducible in fresh and warm environments

- `mine_attempt_logs.py`
  - recursively discovers run directories under `artifacts/telemetry/**`, `Problems/**/Reports/**`, or `docs/examples/**`
  - aggregates minimal metrics:
    - triage distribution
    - retrieval HIT/MISS
    - judge/signals counts
    - runtime tool usage counts from `AttemptLog.exec_spans[*].cmd` (`binary_counts` + `command_counts`)
    - promotion/gc counts
  - outputs structured JSON for automations / eval / skills-regeneration

- `compare_bench_reports.py`
  - compares two bench JSON files
  - computes numeric deltas and `*_counts` dict deltas only (no interpretation)
  - outputs stable delta JSON + optional markdown summary

Contract:
- `docs/contracts/BENCH_CONTRACT.md`
