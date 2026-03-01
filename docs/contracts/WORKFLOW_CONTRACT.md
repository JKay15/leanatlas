# WORKFLOW_CONTRACT v0.3 (Phase 2)

This contract defines the **Codex small-loop** and its only exit conditions:
- `SUCCESS` (all gates pass)
- `TRIAGED` (a structured stop with evidence + next actions)

It also defines:
- ProblemState truth-source state machine (`Problems/<slug>/State.json`) and update rules
- Patch scope policy (OPERATOR vs MAINTAINER)
- Progress signals + stagnation controller (adaptive K)
- **Decide = Advisor + Judge** (Codex proposes; deterministic Judge decides)
- Required audit artifacts (`AttemptLog.jsonl`, `RunReport.json`, and updated `State.json`) for reproducibility

---

## 0) Terms

- **Problem**: a directory `Problems/<problem_slug>/`.
- **ProblemState**: `Problems/<problem_slug>/State.json` (problem state machine source of truth; see `PROBLEM_STATE_CONTRACT`)
- **problem_slug**: the path-safe identifier `<problem_slug>` used in `Problems/<problem_slug>/`.
- **Run**: one invocation of the Codex small-loop that produces a `Reports/<run_id>/` output directory.
- **Attempt**: one iteration inside a run: snapshot → retrieval ladder → patch → build/check → analyze → decide.
- **Snapshot**: record baseline hashes/metadata needed to compute touched files and progress signals deterministically.
- **Patch scope**: the set of source files Codex is allowed to edit during attempts (OPERATOR mode).
- **Progress signals**: measurable indicators that the run is moving forward (diagnostics change, new lemma hit, etc.).
- **Advisor**: Codex's non-deterministic “proposal layer”: hypotheses + next actions. Advisor output is logged but **never authoritative**.
- **Judge**: deterministic decision layer that outputs `CONTINUE` or `TRIAGED` (or `SUCCESS`) based only on facts + budgets + contract rules.
- **Budget controller**: caps attempts/resources and triggers TRIAGED when progress stalls or limits are exhausted.
- **Budget limits**: deterministic caps such as max_attempts / max_steps / max_external_queries / max_wall_time_ms.
- **Budget counters**: deterministic usage counters such as attempts_used / steps_used / external_queries_used / wall_time_ms.

Design principle:
- **Codex may be clever; the Judge must be reproducible.**
- We maximize utility by letting Codex propose actions and explanations, while keeping exits and permissions mechanically enforceable.

---

## 1) Required outputs (Phase 2)

Every run MUST produce:
- `RunReport.json`  (see schema)
- `RunReport.md`
- `RetrievalTrace.json` (see schema)
- `AttemptLog.jsonl` (each line validates)

The run report MUST include:
- `targets` (exactly one MAIN)
- `stages` (retrieval/build/verify)
- `diagnostics` (at least one error diagnostic when TRIAGED)
- `hotspots` (TRIAGED only; each hotspot includes a stage)

The retrieval trace MUST include:
- a domain section
- a budget section
- ordered steps with contiguous `step_index`

---

## 2) Patch scope policy

### 2.1 OPERATOR mode (default)

Codex MAY edit only the following **source** files under the current problem:

Allowed edits:
- `Problems/<problem_slug>/Proof.lean`
- `Problems/<problem_slug>/Cache.lean`
- `Problems/<problem_slug>/Cache/**/*.lean`   (recommended for research-scale problems)
- `Problems/<problem_slug>/Scratch.lean`      (may contain `sorry`, but MUST NOT be imported by Proof/Cache)

Allowed file creation:
- New `.lean` files ONLY under `Problems/<problem_slug>/Cache/`.

Forbidden edits (trigger TRIAGED immediately):
- `Problems/<problem_slug>/Spec.lean`  (changes the statement/assumptions)
- Any file outside `Problems/<problem_slug>/` (cross-problem or system pollution)
- Any file under `LeanAtlas/**`, `tools/**`, `docs/contracts/**`, `.github/**`  (system/library/contracts)

Forbidden (metadata / non-Lean):
- Non-`.lean` files under the problem directory (e.g. README, yaml) are treated as metadata edits and are forbidden in OPERATOR mode.

Ignored paths (system outputs; do not count as patch scope):
- `Problems/<problem_slug>/Reports/**`
- `artifacts/**`
- `.lake/**`
- `.cache/**`

### 2.2 MAINTAINER mode (local only)
Maintainers may edit system/library/contracts, but MUST:
- create an ExecPlan under `docs/execplans/`
- update tests/fixtures accordingly
- bump versions for any breaking schema/contract change

---

## 3) Small-loop algorithm (contract)

A run proceeds as:

1) **Snapshot**
   - Record baseline hashes/metadata for all source files in scope (for patch scope evaluation).
   - Initialize budgets and counters.

2) **Retrieval ladder** (recorded into `RetrievalTrace.steps`)
   - ENVIRONMENT (current imports)
   - TOOLBOX_SAME_DOMAIN
   - SEEDS_SAME_DOMAIN
   - MATHLIB_SAME_DOMAIN
   - DOMAIN_EXPAND
   - EXTERNAL_SEARCH (candidates MUST be locally validated)

3) **Attempt**
   - Apply a bounded patch to allowed files (Proof/Cache/Cache/**/Scratch).
   - Run build/check (`lake build` or Lean LSP equivalent).
   - Update diagnostics + stage statuses.
   - Compute progress signals (see §4).
   - Append an AttemptLog line (facts + Judge + optional Advisor).

4) **Decide = Advisor + Judge**
   - **Advisor (Codex)** proposes:
     - hypotheses (what kind of failure this is)
     - candidate next actions (e.g. add import, refactor proof, request GPTPro replan)
     - short explanations referencing evidence ids (diagnostic_ids / trace_step_indices / target_id)
     - Advisor output is logged under `AttemptLog.advisor_decision` but is not authoritative.
   - **Judge (deterministic)** decides:
     - If success gates pass → `SUCCESS`
     - Else if patch scope is violated → `TRIAGED (ESCALATE; SCOPE_VIOLATION)`
     - Else if an escalation trigger is proven (assumption/definition/statement issues, tooling failure) → `TRIAGED (ESCALATE)`
     - Else if budgets exhausted / stagnation exceeded K → `TRIAGED (FIXABLE or ESCALATE based on triggers)`
     - Else → `CONTINUE`

---

## 4) Progress signals + stagnation controller ("net progress")

Progress signals are deterministic and must be recorded per attempt:

### 4.1 Signals (minimum required)
Each attempt MUST compute:

- `diag_fingerprint`: a stable hash of *error* diagnostics (file + range + message), sorted.
- `diag_changed`: whether fingerprint differs from previous attempt.
- `new_retrieval_hit`: whether a new chosen candidate lemma was HIT since last attempt.
- `imports_changed`: whether imports/open-scoped changed (within allowed files).

Optional (recommended when LSP supports it):
- `goal_snapshot_hash` + `goal_changed`

### 4.2 Stagnation
An attempt is **stagnant** when:
- `diag_changed == false`
- `new_retrieval_hit == false`
- `imports_changed == false`
- (and if goal hash is present) `goal_changed == false`

### 4.3 Adaptive K (max consecutive stagnant attempts)
K is NOT a single constant. It depends on the suspected failure family:

Default K by category family:
- `ASSUMPTION` / `DEFINITION` / `STATEMENT`: K = 0 (immediate ESCALATE)
- `TOOLING`: K = 1 (retry once; then TRIAGED)
  - If `signals.tooling_failed = true`, Judge may TRIAGE immediately with reason `TOOLING_FAILURE`.
- `IMPORT` / `NAME`: K = 2
- `TYPE`: K = 4
- `TACTIC`: K = 6
- `BUDGET`: K = 2 (budget exhaustion is the stop condition; the family itself is not immediate)
- `UNKNOWN`: K = 2

When K is reached → TRIAGED with evidence (fingerprints, trace indices, diagnostics).


### 4.4 Budgets (resource caps)

The small-loop MUST enforce deterministic budget limits. At minimum:

Limits:
- `max_attempts`: maximum number of attempts in a run.
- `max_steps`: maximum number of retrieval steps (from `RetrievalTrace.budget.max_steps`).
- `max_external_queries`: maximum number of external search queries (from `RetrievalTrace.budget.max_external_queries`).
- `max_wall_time_ms`: optional wall-clock cap for the run (best-effort; recorded for audit).

Counters (recorded per attempt in AttemptLog):
- `attempts_used`
- `steps_used`
- `external_queries_used`
- `wall_time_ms`

Budget exhaustion triggers:
- If any counter exceeds its limit → Judge MUST output `TRIAGED` with `reason_code=BUDGET_EXHAUSTED`.
- Budget exhaustion is `ESCALATE` only when the suspected family requires escalation (K=0), otherwise `FIXABLE`.

Design note:
- Limits are deterministic; Advisor suggestions do not override them.
- Counter sources must be auditable (e.g. `steps_used = RetrievalTrace.budget.used_steps`).
---

## 5) TRIAGED classification rules (mechanical)

TRIAGED MUST include:
- `triage.level` in {ESCALATE, FIXABLE}
- `triage.category` as `{family, code, standard?}` (open code; bounded family)
- `triage.evidence.diagnostic_ids` (must refer to `RunReport.diagnostics[].id`)
- `triage.next_actions` (at least one actionable item)

### 5.1 Level selection
- `ESCALATE` when the run requires changes outside Proof/Cache scope or requires a human/GPTPro mathematical decision:
  - Spec changes (missing assumptions, statement reformulation)
  - Definition alignment / bridge decisions
  - Suspected false statement
  - External tool failure without safe offline fallback
  - Patch scope violation
- `FIXABLE` when the issue is likely within proof engineering but the run is out of budget or needs a different proof plan:
  - e.g. repeated tactic failures / type mismatches with no progress

---

## 6) AttemptLog.jsonl (audit trail)

Each attempt MUST append exactly one JSON object line to `AttemptLog.jsonl`.
The line MUST validate against `docs/schemas/AttemptLogLine.schema.json`.

AttemptLog is the authoritative audit trail for:
- touched file paths (patch scope audit)
- per-attempt progress signals
- per-attempt stage statuses
- deterministic Judge decisions and reasons
- optional Advisor proposals (Codex) with evidence refs

### 6.1 Evidence-chain upgrade: exec_spans (Phase6+)
AttemptLog MUST include runner-captured command execution evidence:
- `exec_spans[]` is written by deterministic tooling (not by Codex).
- Every span MUST include: `cmd`, `cwd`, `exit_code`, `stdout_path`, `stderr_path`, `stdout_sha256`, `stderr_sha256`, `duration_ms`.
- `stdout_path/stderr_path` MUST exist within the run directory (see `docs/contracts/REPORTING_CONTRACT.md`).

Implementation rule:
- All command execution inside the proof-loop runner MUST go through `tools/workflow/run_cmd.py`.

Advisor outputs MUST NOT include chain-of-thought. They should be concise, evidence-linked, and operational.

---

## 7) E2E golden test suite (Phase 2 acceptance)

Phase 2 defines an E2E matrix with profiles:

- `smoke` (PR gate; minimal closure)
- `core`  (PR gate; covers major categories)
- `nightly` (extended; performance/tooling regressions)

E2E tests MUST be deterministic:
- Fixable cases use deterministic patch sequences under `patches/`.
- TRIAGED cases validate that the system exits with correct classification and evidence.

See `docs/contracts/E2E_CONTRACT.md` and `tests/e2e/README.md` for the full matrix.
