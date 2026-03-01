# Agents KB (knowledge base)

This directory stores **stable facts + verifiable patterns**.
KB entries are lighter/shorter than Skills.

Design intent:
- Convert frequent TRIAGED/failure patterns into reusable repair steps (SRE runbook style).
- Every KB entry must be reproducible and regressable: symptoms, reproduction, fix, regression check.
- New patterns should land in KB first; upgrade to a Skill only if it becomes multi-step/needs tool calls.

Recommended growth loop (aligned with Phase6):
- Mine AttemptLog/RunReport/diagnostics → template extraction + clustering → `kb_suggestions.json` (automation).
- Land KB updates via minimal Change Proposals.
- Prove improvement via Agent eval (metrics go up; no unacceptable regressions).

Suggested tool entrypoint:
- `uv run --locked python tools/bench/mine_kb_suggestions.py --in <run_root> --out artifacts/skills_regen/kb_suggestions.json`

Contract:
- `docs/contracts/SKILLS_GROWTH_CONTRACT.md`
