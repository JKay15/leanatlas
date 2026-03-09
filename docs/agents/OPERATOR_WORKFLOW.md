# OPERATOR workflow (from a fixed Spec to SUCCESS / TRIAGED)

This is the **use-phase** manual: after someone clones LeanAtlas, Codex should follow this workflow by default.

Default mode is OPERATOR.
MAINTAINER is enabled only when a human has created a local root `AGENTS.override.md` (gitignored).

Current LOOP mainline entry and boundary reference:
- `docs/agents/LOOP_MAINLINE.md`
- `.agents/skills/leanatlas-loop-mainline/SKILL.md`
- Use these to understand the current mainline system surface, but stay inside OPERATOR patch boundaries unless a human explicitly enables MAINTAINER mode.

Reusable/non-LeanAtlas context entry:
- `docs/setup/LOOP_LIBRARY_QUICKSTART.md`
- `.agents/skills/loop-mainline/SKILL.md`
- These are for understanding the reusable LOOP surface only; OPERATOR work remains bounded by this workflow's patch scope.

LeanAtlas wrapper mapping:
- conversation Codex = root supervisor kernel for LeanAtlas task routing
- OPERATOR still remains inside this workflow's patch scope unless a human explicitly enables MAINTAINER
- if a non-trivial direct/manual fallback is ever claimed on a maintainer-side subtree, it must be backed by the session-issued root exception artifact, i.e. the root-issued exception artifact for the active session, rather than ad-hoc chat judgment

## Environment setup (one-time)
This is not theory. It exists so Codex knows where dependencies live and how to verify them.

Required:
- Lean + Lake + mathlib (truth source via `lake build`)
- Python 3 (deterministic gates/tests)

Strongly recommended (MCP acceleration):
- `lean-lsp-mcp`: `docs/setup/external/lean-lsp-mcp.md`
- `rg` (ripgrep): `docs/setup/external/ripgrep.md`

Verification:
- fast deterministic gates (no MCP required): `uv run --locked python tests/run.py --profile core`
- dependency smoke (requires external tools installed): `uv run --locked python tests/run.py --profile nightly`

If MCP is unavailable, Codex must downgrade (never block):
- `docs/contracts/MCP_LEAN_LSP_MCP_ADAPTER.md`

## 0) Inputs, goal, and hard boundaries

LeanAtlas allows you to move fast, but not to move unverified.
Rules: `docs/contracts/AI_NATIVE_ENGINEERING_CONTRACT.md`.

### Inputs (must be prepared upstream)
OPERATOR assumes a problem directory already exists:
- `Problems/<problem_slug>/Spec.lean` is written by a human (or upstream GPTPro) and is treated as a **problem contract**.
- `Problems/<problem_slug>/README.md` may contain the natural-language statement and definitions.

Codex in OPERATOR mode must **not** edit Spec/README. If the Spec is wrong or missing assumptions, the correct outcome is TRIAGED.

### Repository-external paper ingress (hard rule)
LeanAtlas OPERATOR workflow does not automatically attach to paper sources outside this repository. If the human points Codex at a LaTeX/PDF file elsewhere on disk, treat that as an external source, not as an in-repo LeanAtlas problem yet.

Before running the OPERATOR loop:
- either ingress the paper into LeanAtlas-controlled scope such as `.cache/leanatlas/tmp/<paper_id>/source/**`
- or translate it into a prepared `Problems/<problem_slug>/` problem contract inside the repository

If neither has happened, do not silently act as if LeanAtlas `AGENTS.md` / skills already govern that external file; say that ingress is required first.

### Goal
Given `Problems/<problem_slug>/`:
- either produce **SUCCESS**: `Proof.lean` (and any required `Cache/**`) compiles, with no `sorry`
- or produce **TRIAGED**: structured evidence + concrete next actions for upstream (GPTPro/human) to fix the Spec or assumptions

### PatchScope (OPERATOR)
Allowed edits:
- `Problems/<slug>/Proof.lean`
- `Problems/<slug>/Cache.lean` and `Problems/<slug>/Cache/**/*.lean`
- `Problems/<slug>/Scratch.lean` (may contain `sorry`, but must not be imported by official files)

Forbidden edits (touching any of these must lead to TRIAGED):
- `Problems/<slug>/Spec.lean` (changing the problem contract)
- anything under `LeanAtlas/**`, `tools/**`, `docs/contracts/**`, `.github/**`
- any other problem directory

Note: report artifacts under `Problems/<slug>/Reports/**` are **ignored** by PatchScope (runner outputs).

## 1) Run the small loop (Snapshot → Retrieval → Attempt → Decide)

This loop must produce auditable artifacts:
- `RunReport` / `RetrievalTrace` / `AttemptLog`

### 1.1 Create a run_id and Reports dir
- Suggested run_id: `YYYYMMDD_HHMMSS_<short>` using only `[A-Za-z0-9._-]`
- Create: `Problems/<slug>/Reports/<run_id>/`

### 1.2 Snapshot
Record (AttemptLog first line):
- hashes of relevant source files (Proof/Cache/**/Scratch/Spec)
- budget limits (max_attempts/max_steps/max_external_queries/max_wall_time_ms)
- budget counters initialized to 0
- current import summary (imports in Proof/Cache)

### 1.3 Retrieval ladder (do not reinvent wheels)
Write every step to `RetrievalTrace.steps[]`.

Recommended order:
1) **In-context** (current imports + local context): LSP diagnostics / code actions / local search
2) **Local library**: Toolbox, then Seeds (domain-pruned)
3) **mathlib**: domain-pruned first, then expand if needed
4) **External**: candidates only; everything must be validated locally (exists + type matches)

MCP acceleration (optional, must be downgradeable):
- If `lean-lsp-mcp` is configured and healthy: use it primarily for step (1).
- If MCP times out / errors / is missing: downgrade to pure local methods (`lake build` diagnostics parsing, repo grep, etc.).
- All MCP calls must be logged (tool name, latency, status) in AttemptLog and referenced from RetrievalTrace.

Contracts:
- `docs/contracts/MCP_ADAPTER_CONTRACT.md`
- `docs/contracts/MCP_LEAN_LSP_MCP_ADAPTER.md`

For each retrieval step record:
- layer
- action
- result (HIT/MISS/ERROR)
- budget counters (steps_used / external_queries_used)

### 1.4 Attempt (one controlled modification)
Each attempt includes:
- produce a patch (PatchScope-compliant)
- run verification (build a minimal target when possible)
- capture diagnostics (file/range/message/severity) into RunReport and AttemptLog

### 1.5 Decide (Judge + Advisor)
- **Judge** (deterministic) decides using only:
  - PatchScope (violation → TRIAGED)
  - budgets (exhausted → TRIAGED with `BUDGET_EXHAUSTED`)
  - stagnation (no net progress for K attempts → TRIAGED)
  - SUCCESS condition (build OK + verify OK + no `sorry`) → SUCCESS

- **Advisor** (optional, non-deterministic) may add:
  - hypotheses about why it failed
  - proposed next actions
  - must cite evidence (`diagnostic_ids`, `trace_step_indices`) and must not override the Judge

## 2) Required exit artifacts
Regardless of SUCCESS or TRIAGED, write:
- `RunReport.json`
- `RunReport.md`
- `RetrievalTrace.json`
- `AttemptLog.jsonl`

### SUCCESS acceptance
- `Proof.lean` / `Cache/**` / `Spec.lean`: no `sorry`
- `lake build` passes
- `RunReport.status = SUCCESS`
- `RunReport.verification.no_sorry = true`

### TRIAGED acceptance
- `RunReport.status = TRIAGED`
- must include:
  - `stages` (where in the pipeline the failure occurred)
  - `diagnostics` (≥1 error with a range)
  - `hotspots` (≥1, includes stage and cites `diagnostic_ids`)
  - `triage.category` (bounded family + open code)
  - `triage.next_actions` (≥1 executable action)
  - `judge.reason_code` (e.g. `SCOPE_VIOLATION`, `BUDGET_EXHAUSTED`, `ERROR_OUTSIDE_SCOPE`)

## Common local commands
- build: `lake build`
- tests: `lake test` (if configured) or `uv run --locked python tests/run.py --profile core`
- lint: `lake lint`

## Cleaning and artifact hygiene
- `Problems/**/Reports/**`, `artifacts/**`, `.cache/leanatlas/**` must be gitignored.
- test/run outputs must land only in those dirs.
- cleaning scripts:
  - `scripts/clean.sh` (safe)
  - `scripts/clobber.sh` (nuclear)

## Background Automations
Maintainers may enable background **Automations** (report integrity, MCP healthchecks, dedup scans, trace mining).
Principles:
- automations do not silently change the platform in OPERATOR loops; platform changes must go via PR.
- findings are structured JSON + optional fix PRs.

See: `docs/agents/AUTOMATIONS.md`.

## Feedback-aware operation

If the human provides feedback (friction, missing steps, unclear rule names, etc.),
Codex must not treat it as a one-off patch.

Follow: `docs/agents/FEEDBACK_LOOP.md`.
