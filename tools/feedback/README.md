# tools/feedback

Deterministic utilities for user-chat feedback deposition and governance.

## Entry script

- `mine_chat_feedback.py`
- `append_feedback_ledger.py`
- `build_traceability_matrix.py`

## Contracted I/O

- Input inbox (default): `artifacts/feedback/inbox/**`
- Output digest: `artifacts/feedback/chat_feedback/latest.json`
- Append-only ledger: `artifacts/feedback/ledger/feedback_ledger.jsonl`
- Traceability matrix: `artifacts/feedback/traceability/latest.csv` + `latest.json`

The digest is designed for automation probes (`advisor.when=findings`) and for
maintainer triage into:

- `docs/contracts/**`
- `docs/agents/**`
- `.agents/skills/**`
- `tests/**`

## Example

```bash
uv run --locked python tools/feedback/mine_chat_feedback.py \
  --in-root artifacts/feedback/inbox \
  --out artifacts/feedback/chat_feedback/latest.json

uv run --locked python tools/feedback/append_feedback_ledger.py \
  --digest artifacts/feedback/chat_feedback/latest.json \
  --ledger artifacts/feedback/ledger/feedback_ledger.jsonl \
  --summary-out artifacts/feedback/ledger/latest_append_summary.json

uv run --locked python tools/feedback/build_traceability_matrix.py \
  --ledger artifacts/feedback/ledger/feedback_ledger.jsonl \
  --out-csv artifacts/feedback/traceability/latest.csv \
  --out-json artifacts/feedback/traceability/latest.json \
  --strict-closed
```
