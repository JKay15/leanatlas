# Feedback loop: when user feedback should update docs/skills/tests

LeanAtlas is not “one shot coding”. It is a **living system**.
If a user reports friction and Codex fixes it once but leaves the docs unchanged,
the same failure will repeat.

This document defines a disciplined feedback loop that is:

- **responsive** (does not ignore feedback)
- **selective** (does not dump every sentence into a random doc)
- **auditable** (doc changes are PR-shaped, versioned, and test-backed)

## 1) Classify feedback (before you change anything)

Given a feedback item `F`, classify it into exactly one primary class:

1. **Spec/Contract drift**
   - The documented behavior or contract is wrong / incomplete.
   - Example: “E2E should use one shared workspace, but docs still describe per-case workdirs.”

2. **How-to gap (operational friction)**
   - The system can do it, but the docs do not tell you how.
   - Example: “I don’t know how to trigger automations locally.”

3. **Bug or missing test**
   - The documented behavior is correct, but implementation deviates.
   - Example: “The runner claims it streams logs, but stdout is silent.”

4. **Preference / one-off**
   - Personal preference or a non-repeatable local condition.
   - Example: “I prefer shorter file names.” / “My Wi‑Fi was down.”

## 2) Decide whether docs must change

Rules (ordered):

- **MUST update docs** for (1) Spec/Contract drift.
- **SHOULD update docs** for (2) How-to gap.
- **MUST update tests (and usually docs)** for (3) Bug/missing test.
- **DO NOT update docs** for (4) Preference/one-off.
  - Instead: record it as a local config/flag request or a future improvement idea.

If you decide “no docs change”, you MUST write a short justification in the run report
or the change proposal discussion. Silence is not allowed.

## 3) Where to put the update (routing)

LeanAtlas uses **four doc types** (keep them distinct):

- **Contracts** (`docs/contracts/**`): hard rules, schemas, gates, invariants.
- **Agent manuals** (`docs/agents/**`): how Codex should operate step-by-step.
- **Setup** (`docs/setup/**`): installation and verification of external tools.
- **Knowledge base** (`docs/agents/kb/**`): stable patterns and repair playbooks.

Routing table:

- Hard policy / schema / invariants → `docs/contracts/**`
- “How do I run X?” → `docs/agents/**` or `docs/setup/**`
- “This failure repeats across problems” → `docs/agents/kb/**` + skill updates
- “Codex forgot rule Y” → the relevant `SKILL.md` first paragraph + must-run checks

## 4) Standard output (Change Proposal)

When docs/tests should change, produce a **PR-shaped minimal patch**:

1) Update the relevant doc(s).
2) Add/adjust tests so the feedback does not regress.
   - Register tests in `tests/manifest.json` and `docs/testing/TEST_MATRIX.md`.
3) Run verification commands and attach evidence in logs/artifacts.

This follows `docs/contracts/AI_NATIVE_ENGINEERING_CONTRACT.md`.

## 4.1) Chat feedback deposition pipeline (operational)

To avoid losing user feedback from day-to-day chat prompts, LeanAtlas uses a
deterministic inbox -> digest pipeline:

1) Append raw feedback snippets under `artifacts/feedback/inbox/**`.
2) Run `python tools/feedback/mine_chat_feedback.py`.
3) Consume `artifacts/feedback/chat_feedback/latest.json` for advisor triage.
4) Append new items to `artifacts/feedback/ledger/feedback_ledger.jsonl`.
5) Build traceability matrix at `artifacts/feedback/traceability/latest.csv`.

Important filtering rule:

- Do **not** dump full chat transcripts or all user prompts into inbox.
- Inbox must contain only curated feedback candidates, for example:
  - `feedback: ...`
  - `issue: ...`
  - `request: ...`
  - `[feedback] ...`
- Untagged text is ignored by the miner on purpose.
- If a human explicitly requests immediate deposition, use
  `tools/index/force_deposit.json` -> `feedback[]` (still governed by the same required fields).

Automation coverage:

- `nightly_chat_feedback_deposition` runs this pipeline continuously.
- Advisor probe watches `new_items_count` in `artifacts/feedback/ledger/latest_append_summary.json`
  and opens change proposals only when new items are appended.

Required fields per deposited item:

- `feedback_id`
- `triage_class`
- `severity` (`S0..S3`)
- `sla_hours`
- `required_actions`
- `closure_criteria`
- `links.{prs,tests,docs,release_notes}`

Governance contract:

- `docs/contracts/FEEDBACK_GOVERNANCE_CONTRACT.md`

Expected routing from digest category:

- `contracts` -> `docs/contracts/**`
- `docs` -> `docs/agents/**`
- `skills` -> `.agents/skills/**` or `docs/agents/kb/**`
- `tests` -> `tests/**`
- `tooling` -> `tools/**`

## 5) When to grow skills vs KB

Use this rule of thumb:

- If the pattern is **rare but critical**, update the relevant `SKILL.md` directly.
- If the pattern is **recurring**, add a KB entry and let weekly mining automate discovery.

See also:
- `docs/contracts/SKILLS_GROWTH_CONTRACT.md`
- `docs/contracts/SKILLS_REGEN_CONTRACT.md`

## 6) Closed-loop acceptance (must stay true)

- Promotion/GC continuous checks are automated by `nightly_phase3_governance_audit`.
- Skills deposition is automated by `weekly_kb_suggestions` (telemetry mining + regen audit + stub plan).
- User chat feedback deposition is automated by `nightly_chat_feedback_deposition`.

If any one of these automations is removed or downgraded, the closed-loop claim is invalid.

## References (industry patterns)

This policy borrows from:
- docs-as-code (docs reviewed/merged like code)
- Diátaxis-style doc type separation (tutorial/how-to/reference/explanation)
- SRE-style postmortem thinking (fix the system, not just the instance)
