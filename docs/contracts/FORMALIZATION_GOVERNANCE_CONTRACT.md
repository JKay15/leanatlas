# FORMALIZATION_GOVERNANCE_CONTRACT v0.1

This contract defines deterministic gate/governance artifacts for formalization workflow.

## 1) Canonical governance artifacts
- Proof completion worklist:
  - schema: `docs/schemas/ProofCompletionWorklist.schema.json`
- Decision apply report:
  - schema: `docs/schemas/ProofCompletionDecisionApplyReport.schema.json`
- Formalization gate report:
  - schema: `docs/schemas/FormalizationGateReport.schema.json`
- Agent fidelity review report:
  - schema: `docs/schemas/AgentFidelityReview.schema.json`
- ExternalSourcePack:
  - schema: `docs/schemas/ExternalSourcePack.schema.json`

## 2) Proof completion state model
Canonical completion states (claim/proof unit):
- `NEW`
- `CODEX_ATTEMPTED`
- `GPT52PRO_ESCALATED`
- `TRIAGED_UNPROVABLE_CANDIDATE`
- `COMPLETED`

Hard rules:
- State transitions MUST be append-only and evidence-backed.
- `TRIAGED_UNPROVABLE_CANDIDATE` requires explicit blocker evidence refs.
- External dependency unresolved status may block completion but must be explicit.

## 3) Gate semantics
Formalization gate and mapping gate are independent but composable:
- Formalization gate: proof completeness + anti-cheat + dependency resolution policy.
- Mapping gate: declaration/object to clause/atom alignment completeness/correctness.

Committed front-end governance helpers that feed those gates include:
- human ingress through `ExternalSourcePack`
- source enrichment from LaTeX/Bib evidence, with PDF roots accepted only as bounded coverage inputs
- review todo generation for mapping triage
- reverse-link resync for annotation-backed alignment refresh

Decision rule (deterministic):
- final pass requires both gates pass,
- if one fails and is fixable: continue loop,
- if non-fixable with sufficient evidence: triage.

## 3.1) Canonical formalization governor entrypoint
- Deterministic governor implementation:
  - `tools/workflow/formalization_governor.py`
- Canonical reason codes:
  - `DUAL_GATE_PASS`
  - `FIXABLE_GATE_FAILURE`
  - `NON_FIXABLE_BLOCKER`
  - `GOVERNOR_STAGNATION`
  - `GOVERNOR_REPAIR_BUDGET_EXHAUSTED`
- Required behavior:
  - identical semantic input must yield identical governor output,
  - `EXTERNAL_DEPENDENCY_PENDING` is non-fixable in local loop and must TRIAGE,
  - repair loop budget and repeated-fingerprint stagnation are deterministic stop rules.

## 4) Anti-cheat and semantic-placeholder policy
Non-exhaustive blocker codes:
- `OPAQUE_HYPOTHESIS_PATTERN`
- `SEMANTIC_PLACEHOLDER_NO_EXTERNAL`
- `PROOF_TOO_SHORT`
- `EXTERNAL_DEPENDENCY_PENDING`

Policy:
- these codes MUST be surfaced by deterministic gate reports,
- agent review may add advisory findings but cannot suppress deterministic blockers.

## 5) Agent review closeout policy
For non-trivial formalization changes, closeout MUST include one of:
- `REVIEW_RUN`: with prompt/response evidence refs,
- `REVIEW_SKIPPED`: with reason code and evidence refs.

Reason-code examples:
- `TRIAGED_TOOLING`
- `SCOPE_TEXT_ONLY`
- `USER_EXPLICIT_SKIP`
- `NO_EFFECTIVE_CHANGE`

## 6) Compatibility and migration
Experimental artifacts remain valid evidence sources but non-authoritative.
The authoritative outputs for workflow/Judge integration are the five canonical governance artifacts above.
