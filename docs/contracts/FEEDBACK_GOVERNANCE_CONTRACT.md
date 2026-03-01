# FEEDBACK_GOVERNANCE_CONTRACT

Purpose: make user-chat feedback deposition auditable, append-only, and traceable to
engineering actions (docs/tests/tools/skills/release).

## 1) Data flow (deterministic)

1. Curated inbox snippets: `artifacts/feedback/inbox/**`
2. Digest extraction: `tools/feedback/mine_chat_feedback.py`
   - output: `artifacts/feedback/chat_feedback/latest.json`
   - optional human-forced deposition source: `tools/index/force_deposit.json` -> `feedback[]`
3. Append-only ledger: `tools/feedback/append_feedback_ledger.py`
   - output: `artifacts/feedback/ledger/feedback_ledger.jsonl`
   - summary: `artifacts/feedback/ledger/latest_append_summary.json`
4. Traceability matrix: `tools/feedback/build_traceability_matrix.py`
   - output: `artifacts/feedback/traceability/latest.csv`
   - summary: `artifacts/feedback/traceability/latest.json`

No LLM calls are allowed in these steps.

Forced feedback items are allowed, but they must still emit the same governance fields
(`triage_class`, `severity`, `sla_hours`, `required_actions`, `closure_criteria`, links).

## 2) Severity + SLA (required)

Severity must be one of:

- `S0` (critical): SLA `<= 4h`
- `S1` (high): SLA `<= 24h`
- `S2` (medium): SLA `<= 72h`
- `S3` (low): SLA `<= 168h`

Every digest item and ledger line must include:

- `severity`
- `sla_hours`

## 3) Triage class (required)

Every feedback item must classify into exactly one:

- `contract_drift`
- `how_to_gap`
- `bug_missing_test`
- `one_off_preference`

Every item must include:

- `required_actions`
- `closure_criteria`

## 4) Append-only rule

- `feedback_ledger.jsonl` is append-only.
- Existing lines must never be rewritten in-place by automation.
- Dedup key is `feedback_id`; the same `feedback_id` must not be appended twice.

## 5) Traceability rule

Traceability links are stored on each ledger line under:

- `links.prs[]`
- `links.tests[]`
- `links.docs[]`
- `links.release_notes[]`

Closed statuses are: `closed`, `resolved`, `done`.

If an item is closed, it should have at least one traceability link.

## 6) Automation integration (required)

`nightly_chat_feedback_deposition` must include deterministic steps for:

- digest extraction
- ledger append
- traceability build

Advisor triggering should use `latest_append_summary.json` so Advisor runs on
newly deposited items rather than repeatedly on old backlog.
