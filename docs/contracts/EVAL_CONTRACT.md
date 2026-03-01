# EVAL_CONTRACT v0 (Phase 5)

Purpose: provide a **minimal runnable eval/bench metrics framework** for:
- regression tracking
- tuning
- automation health monitoring

This contract defines only:
- **where eval artifacts land**
- **the output JSON shape**

It does not define Phase3/4 business thresholds or gate semantics.

## 1) Definitions

- **Eval**: quantitative evaluation over one or more runs/processes.
- **Signal**: one comparable metric item (count/rate/latency, etc.). Must be machine-readable and regressable.
- **Deterministic eval**:
  - must not call an LLM
  - same inputs should yield stable outputs
  - floats are allowed, but formatting/rounding must be fixed

## 2) Artifact location (mandatory)

Eval outputs must be written to:
- `artifacts/evals/<eval_id>/<stamp>/eval.json`

Where:
- `<eval_id>`: snake_case or kebab-case
- `<stamp>`: UTC timestamp or a run_id (for archiving multiple runs; does not need to be deterministic)

Core rule:
- Each run must write its outputs **only** inside its own directory so it can be archived, compared, and cleaned safely.

## 3) Output shape (V0)

`eval.json` must include:

- `schema: string` (e.g. `leanatlas.eval`)
- `schema_version: string`
- `eval_id: string`
- `input_roots: array[string]`
- `signals: object`
  - values must be numbers (int or float)
  - recommended: use floats with fixed decimal formatting
- `notes: array[string]` (may be empty; used to record missing-data or downgrade warnings)

Recommended optional fields:
- `breakdown: object` (distributions/buckets; counts and ratios only; no business interpretation)
- `artifacts: array[string]` (extra output file paths to archive)

## 4) Minimal recommended signal set (not mandatory)

For cross-phase trend tracking, Phase5 recommends (names only; no thresholds):

- `triage.distribution.*` (TRIAGED family/category distribution from RunReport/AttemptLog)
- `retrieval.hit_rate` (from RetrievalTrace)
- `workflow.gc.*` (GC action counts / success rate from GCReport)
- `workflow.promotion.*` (Promotion success rate from PromotionReport)

Note:
- Signals define only “name + numeric value”.
- Thresholds belong to Phase3/4 gate semantics.
