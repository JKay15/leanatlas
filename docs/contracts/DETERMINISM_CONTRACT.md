# DETERMINISM_CONTRACT v0.1 (Phase 1)

This contract keeps LeanAtlas artifacts diff-friendly and reproducible.

## 1) Canonical JSON formatting (committed files)
All committed JSON files under:
- `docs/examples/**`
- `docs/schemas/**`
- `tests/schema/fixtures/**`

MUST be in canonical formatting:
- UTF-8
- `json.dumps(..., indent=2, sort_keys=True, ensure_ascii=False)`
- trailing newline

Rationale:
- Prevents noisy diffs and makes reviews/audits sane.

## 2) RetrievalTrace invariants (committed examples)
For `docs/examples/reports/*/RetrievalTrace.json`:
- `budget.used_steps == len(steps)`
- steps are sorted by `step_index`
- `steps[i].step_index == i` for all i
- `budget.used_steps <= budget.max_steps`
- `budget.used_external_queries <= budget.max_external_queries`
