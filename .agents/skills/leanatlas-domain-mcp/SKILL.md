---
name: leanatlas-domain-mcp
description: Use the Domain Ontology MCP (MSC2020 + local overlay) to route a problem into a domain, expand the domain set for retrieval pruning, and record auditable evidence. Enforces “new non-MSC domain requires explicit user consent”.
owner: PHASE-4
---

## Use when
- You need to choose `domain_id` / `msc_codes[]` for a problem and use domain-driven pruning in the retrieval ladder.
- You need to expand a domain into an “expand set” and log DOMAIN_ROUTE / DOMAIN_EXPAND_SET steps in RetrievalTrace.

## Don't use when
- You are about to invent MSC codes or create a new `local:*` domain without explicit user consent.
- The MCP server is unavailable and you would be forced to over-prune (degrade instead: route UNKNOWN, no pruning).

## Outputs
- `Problems/<slug>/Reports/<run_id>/RetrievalTrace.json` updated with:
  - `DOMAIN_ROUTE` step (candidates + chosen + evidence)
  - (optional) `DOMAIN_EXPAND_SET` step
- Optional health evidence:
  - `artifacts/mcp/healthcheck.json`

## Must-run checks
- `uv run --locked python tools/lean_domain_mcp/domain_mcp_server.py --msc2020-mini --smoke`
- `uv run --locked python tools/mcp/healthcheck.py --out artifacts/mcp/healthcheck.json`

## Contracts / docs you MUST follow
- `docs/contracts/MCP_MSC2020_CONTRACT.md` (Domain Ontology MCP: provider+overlay+tools+TDD+degrade)
- `docs/contracts/RETRIEVAL_TRACE_CONTRACT.md` (how to log DOMAIN_ROUTE / DOMAIN_EXPAND_SET)
- `docs/contracts/MCP_ADAPTER_CONTRACT.md` (MCP is an accelerator; must degrade)
- Setup:
  - `docs/setup/external/domain-mcp.md`
  - `docs/setup/external/msc2020.md`

## Capability entrypoints (Phase4 manifest)
- Start server (stdio): `python tools/lean_domain_mcp/domain_mcp_server.py ...`
- Ingest MSC2020 CSV → bundle: `python tools/lean_domain_mcp/ingest_msc2020_csv.py ...`
- Prune helper (optional): `python tools/retrieval/domain_prune.py ...`

---

## Hard constraints
1) **Never invent MSC codes.** If a hint looks like a code, call `domain/validate_hint` (or `domain/lookup`) and verify it exists.
2) **New non-MSC domain is rare and gated:**
   - If you believe MSC2020 cannot cover it and a new `local:*` domain is needed, you MUST stop and ask the user for explicit consent.
   - Without consent: route to `UNKNOWN` and do NOT create/assume a new domain.
3) MCP is optional: if the server is unavailable, you MUST degrade to deterministic fallback (no pruning; or structure-only signal).
4) Every domain routing decision must be auditable in RetrievalTrace (DOMAIN_ROUTE step with candidates+chosen evidence).

---

## Standard playbook

### Step 0) Detect MCP availability (fast)
- If MCP client tooling exists: call `domain/info`.
- If you only have local repo scripts: run `python tools/lean_domain_mcp/domain_mcp_server.py --msc2020-mini --smoke`.

If unavailable/fails: set `fallback_used=true` and proceed with:
- `domain_id="UNKNOWN"`
- do not prune search roots

### Step 1) Normalize inputs
Inputs you may have:
- `problem_text` (the statement / goal)
- `human_hint` (optional; could be `03E20` or “logic / algebraic geometry”)
- `structural_signals` (optional; directory/import clues from Phase3)

Normalize:
- trim whitespace
- keep original hint string for audit

### Step 2) Candidate generation (never skip)
1) If `human_hint` exists: call `domain/validate_hint(hint)`.
   - If it returns strong candidates, keep them as “prior candidates”.
2) Always call `domain/lookup(problem_text, k=K)` (K ~ 8–12).
3) Merge and deduplicate candidates by `id`.
4) Deterministic sort: by `score desc`, then `code asc`.

### Step 3) Final decision (Codex decides, but with evidence)
Choose:
- `domain_id` (coarse bucket): prefer `MSC_<2digits>` derived from the chosen MSC code(s)
- `msc_codes[]` (fine): 0..n (usually 1–3)
- `confidence` (0..1)

Decision rules:
- Prefer MSC2020 domains whenever possible.
- If candidates are low-confidence or contradictory:
  - choose `domain_id="UNKNOWN"` and set `fallback_used=true`
  - continue without pruning (avoid false pruning)

### Step 4) Domain expansion (for retrieval ladder)
Call:
- `domain/expand(codes|ids, up_depth=1, down_depth=0, include_siblings=false)`

Use this “expand set” to drive:
- `TOOLBOX_SAME_DOMAIN`
- `SEEDS_SAME_DOMAIN`
- then `DOMAIN_EXPAND` layer

### Step 5) Roots suggestion (optional pruning)
Call:
- `domain/roots(codes|ids)`

If it reports `missing=true` (no mapping):
- do not prune aggressively
- fall back to repo_root search

### Step 6) Audit logging (RetrievalTrace)
Write a `DOMAIN_ROUTE` step (layer=ENVIRONMENT):
- `candidates[]`: include `id/code/text/score/source_id/evidence`
- `chosen`: include `domain_id/msc_codes/confidence/fallback_used/user_consent`

If you expanded:
- add `DOMAIN_EXPAND_SET` step (layer=DOMAIN_EXPAND) with the returned ids

### Step 7) Rare path: proposing a new local domain
Trigger only if:
- no MSC candidate is above your threshold AND
- the task is clearly outside MSC coverage (e.g. Lean toolchain engineering)

Protocol:
1) Emit a user-facing proposal:
   - proposed `local:<slug>`
   - name/description
   - parent (must be an existing MSC bucket or a stable local root)
   - why MSC is insufficient
2) Ask for explicit consent.
3) If consent is not explicit: STOP creating it; route to `UNKNOWN`.

---

## Output checklist
Before you finish, ensure you have:
- a chosen `domain_id` and (optionally) `msc_codes[]`
- an explicit fallback decision if MCP was missing
- RetrievalTrace DOMAIN_ROUTE evidence captured (no silent routing)
