# BENCH_CONTRACT v0 (Phase 5)

Purpose: turn “statistics over AttemptLog/RunReport/RetrievalTrace/Promotion/GC artifacts” into a **deterministic**, reproducible, automation-consumable engineering component.

This contract constrains only the **bench interface shape**. It does not define Phase3/4 business semantics.

## 1) Definitions

- **Bench**: a script/tool that aggregates metrics over run artifacts.
- **Deterministic bench**: depends only on local file inputs + deterministic algorithms; must not call an LLM; same input must yield byte-stable output (or at least canonical JSON stable output).
- **Input roots** (examples):
  - `artifacts/telemetry/**` (normalized run traces, collected by `tools/bench/collect_telemetry.py`)
  - `Problems/**/Reports/**` (local run dirs, gitignored)
  - `docs/examples/**` (committed minimal examples for core contract tests)

## 2) Artifact locations (mandatory)

Bench outputs must be written to:
- `artifacts/bench/**` (recommended) or
- `.cache/leanatlas/bench/**`

Forbidden:
- writing outputs into version-controlled paths (unless the output is explicitly defined as deterministic regen and has a contract + tests).

## 3) Unified output shape (V0)

Any bench output JSON must include:

- `schema: string` (e.g. `leanatlas.bench.mine_attempt_logs`)
- `schema_version: string` (semantic version; breaking changes must bump)
- `input: string` (input root path; may be relative)
- `summary: object` (must include at least `run_count`)
- `warnings: array[string]` (may be empty; must not replace readable warnings with hard exceptions)

Recommended optional blocks:
- `triage`: distribution stats (counts/ratios only; no business interpretation)
- `retrieval`: HIT/MISS stats (counts/ratios only)
- `attempts`: judge/signals counts
- `tool_usage`: runtime command usage stats from `AttemptLog.exec_spans[*].cmd` (no source-code scanning)
- `promotion`: promotion gate/decision counts (do not interpret gate semantics)
- `gc`: gc action counts (do not interpret policy semantics)

## 4) Failure strategy (must remain usable)

- If the input root does not exist or is empty:
  - still output a valid JSON (`run_count=0`) and record a warning
  - exit code should be 0 by default (so automation dry-run can pass in an empty environment)

- If strict failure is needed (e.g. nightly wants bad data to fail hard):
  - provide `--strict` (or equivalent)
  - in strict mode: parse errors / missing files must return non-zero exit

## 5) Relationship to AUTOMATION

If a bench tool is used by an automation:
- it must be registered in `automations/registry.json` as a deterministic step
- it must have a runnable dry-run (core profile)
- its artifact outputs must be listed in the registry entry
- if `--in artifacts/telemetry` is used, the automation must first run telemetry collection with `--clean`

## 6) Delta comparison (optional but recommended)

If you need stable “today vs yesterday” comparisons:
- use a separate tool to compare two bench JSON outputs
- only compute numeric and `*_counts` deltas
- output delta JSON + optional markdown summary
- do not add business interpretation in the delta tool
