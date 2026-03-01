---
name: leanatlas-skills-growth
description: Maintain and grow LeanAtlas Skills/KB using deterministic evidence from AttemptLog/RunReport telemetry (log-template mining + clustering). Use when updating docs/agents/kb/*, adding/modifying .agents/skills/*, or implementing weekly_kb_suggestions automation. MAINTAINER-only.
---

## Use when
- You are in **MAINTAINER** mode and need to **add/update KB entries** under `docs/agents/kb/*` based on recurring TRIAGED/SUCCESS patterns.
- You are implementing the **skills/KB growth pipeline** (telemetry mining, suggestion generation, regen audit, Change Proposal workflow, eval verification).
- You are running or updating the **weekly_kb_suggestions** automation.

## Don't use when
- You are in **OPERATOR** mode proving a single problem (do not touch global KB/skills).
- You do not have real artifacts (AttemptLog/RunReport) to back the change — skills growth must be evidence-driven.

## Outputs
- `artifacts/skills_regen/kb_suggestions.json`
- `artifacts/skills_regen/view.json`
- `artifacts/skills_regen/audit.json`
- `artifacts/skills_regen/stub_plan.json`
- Change Proposal patch touching:
  - `docs/agents/kb/**` and/or
  - `.agents/skills/**`

## Must-run checks
- `uv run --locked python tools/bench/mine_kb_suggestions.py --in artifacts/telemetry --out artifacts/skills_regen/kb_suggestions.json`
- `uv run --locked python tests/run.py --profile core`

# Skills/KB Growth (Phase6-ready)

## Read first (source of truth)

- `docs/contracts/SKILLS_GROWTH_CONTRACT.md`
- `docs/contracts/AGENT_EVAL_CONTRACT.md`
- KB index: `docs/agents/kb/README.md`
- Automation registry: `automations/registry.json` (see `weekly_kb_suggestions`)

## Workflow (evidence → proposal → eval)

1) **Collect evidence**
   - Ensure you have fresh run artifacts under `artifacts/telemetry/**` (RunReport + diagnostics).

2) **Mine suggestions (deterministic; no LLM)**

```bash
uv run --locked python tools/bench/mine_kb_suggestions.py \
  --in artifacts/telemetry \
  --out artifacts/skills_regen/kb_suggestions.json
```

3) **Run skills regeneration audit + stub planning**

```bash
uv run --locked python tools/coordination/skills_regen.py \
  --repo-root . \
  --out artifacts/skills_regen/view.json \
  --audit-out artifacts/skills_regen/audit.json \
  --check

uv run --locked python tools/coordination/skills_stubgen.py \
  --repo-root . \
  --out artifacts/skills_regen/stub_plan.json
```

4) **Turn suggestions into a Change Proposal**
   - Create a minimal patch:
     - new KB draft in `docs/agents/kb/draft/<id>.md` (or update an existing KB entry)
     - optionally: small skill update if it’s a reusable multi-step procedure
   - Every KB/skill change must include:
     - “symptoms” (what pattern it matches)
     - “fix / procedure” (what to do)
     - “evidence” (run_dir paths or report ids)

5) **Verify via eval / regression**
   - Run the relevant agent eval tasks (Phase6).
   - Confirm at least one metric improves without introducing regressions.

## Non-negotiables

- No “vibe edits”: KB/skill changes must be tied to concrete Pattern signatures.
- Prefer KB first (small, factual). Promote to a Skill only when it’s a repeatable procedure with checks.
- Keep patches mergeable: minimal diffs, no formatting churn.
