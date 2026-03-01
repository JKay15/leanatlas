# PROBLEM_STATE_CONTRACT v0.1

This contract defines `Problems/<problem_slug>/State.json` (**ProblemState**): the **machine-readable source-of-truth lifecycle state machine** for a problem workspace.

It exists to:
- give Codex’s small loop / big loop an explicit “current state” and auditable transitions
- provide Phase3 (Promotion/GC) with **domain-layered** statistics and root selection inputs
- keep automations from “forgetting where a problem is” during unattended runs

Design principle:
> The state machine is an upgrade, not optional.
> Any workflow that tries to infer state by scanning Reports is a temporary hack.

---

## 0) File location and permissions

- Path: `Problems/<problem_slug>/State.json`
- OPERATOR may modify: ✅ (inside the current problem dir)
- MAINTAINER may modify: ✅

---

## 1) Field-level definitions

Schema: `docs/schemas/ProblemState.schema.json`

### 1.1 Required top-level fields

- `version: string`
  - ProblemState format version.

- `problem_slug: string`
  - Must match the directory name under `Problems/`.

- `domain: object`
  - Domain classification used for domain-layered roots/bench/GC clocks.
  - Minimal required field:
    - `domain_id: string`
      - Primary bucket (MSC-derived or LOCAL). Unknown must be `"UNKNOWN"`.
  - Optional:
    - `msc: string[]` (MSC2020 codes like `"11Axx"`)
    - `confidence: number` (0..1)
    - `source: string` (`lean_domain_mcp|manual|heuristic`)
    - `notes: string`

- `status: string`
  - Current lifecycle status (strong enum; no mysticism).
  - Enum (v0.1):
    - `NEW`: just created, no attempt run yet
    - `ACTIVE`: in progress (last run not necessarily success)
    - `SUCCESS`: verified success (`RunReport.status = SUCCESS`)
    - `TRIAGED`: last run exited TRIAGED (needs upstream fix: assumptions/definition/spec)
    - `PAUSED`: human-paused (not set automatically)
    - `ABANDONED`: explicitly abandoned (not set automatically)

- `ever_succeeded: bool`
  - Whether this problem has ever reached SUCCESS.
  - Used for the domain logical clock: domain progress count is the number of distinct `problem_slug`s with `ever_succeeded=true`.

- `counters?: object`
  - Recommended counters for bench and policies.
  - Recommended fields:
    - `attempts`: number
    - `success`: number
    - `triaged`: number

- `last_run: object|null`
  - Pointer summary to the most recent run (avoid “guess latest by filesystem mtime”).
  - Required when not null:
    - `run_id: string`
    - `status: "SUCCESS"|"TRIAGED"`
    - `run_report_path: string` (repo-relative)

---

## 2) State transition rules (mechanical)

ProblemState must be driven by RunReport deterministically.

When a new `RunReport` is produced:
- `status = RunReport.status` (map: SUCCESS→SUCCESS, TRIAGED→TRIAGED)
- `last_run` points to the new report
- `counters.attempts += 1`
- if SUCCESS:
  - `counters.success += 1`
  - `ever_succeeded = true`
- if TRIAGED:
  - `counters.triaged += 1`

Human-only states:
- `PAUSED` / `ABANDONED` may only be set explicitly by a human/maintainer.
- scripts must never enter these automatically.

---

## 3) Update method (avoid hand edits)

Preferred deterministic updater (called at end of the small loop):

- `uv run --locked python tools/problem_state/reconcile.py --problem <slug> --run-report <path>`

Responsibilities:
- validate RunReport schema
- update/create `State.json`
- ensure canonical JSON output (indent=2, sort_keys)

---

## 4) Relationship to Phase3 (GC/PROMOTION)

- GCGate active-problem roots must read `State.json` and group by `domain.domain_id`.
- Domain logical clock is defined as:
  - for each domain, `domain_progress_count(domain) = count(distinct problems with ever_succeeded=true)`.

---

## 5) TDD requirements

Core profile must cover:
- `Problems/_template/**` is not tracked in Repo A (template library is out-of-repo)
- fixtures include positive + negative cases
- `tools/problem_state/reconcile.py` output is schema-valid and canonical JSON
