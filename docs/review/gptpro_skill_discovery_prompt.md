# GPT Pro Prompt: Discover Existing Skills (No New Design)

Use the prompt below directly with GPT Pro.

```text
You are helping me source pre-existing, installable skills for Codex workflows.

Hard constraints:
1) Do NOT design new skills.
2) Do NOT propose custom frameworks unless they already exist and are installable.
3) Only return skills that already exist in public or private repositories, registries, or known curated collections.
4) Every candidate must include evidence links and installation method.
5) If evidence is missing, mark as "unverified" and do not recommend as top choice.

Context:
- Project: LeanAtlas
- We need industrial-grade skills around:
  A) Git discipline (small atomic commits, PR hygiene, release notes, rollback safety)
  B) Lean4/mathlib proof workflows
  C) MCP operations (installation, health checks, fallback/degradation)
  D) Test governance (manifest discipline, contract gates, deterministic reports)
  E) Onboarding quality (new user setup + verification)
  F) Feedback/tool/skills accumulation loops (traceability, closure, anti-drift)

Required output format:
1) "Top candidates" table (ranked)
   Columns:
   - Skill name
   - Source URL
   - Maintainer / owner
   - Last update date
   - Install command(s)
   - Compatibility notes (Codex CLI/App, OS assumptions)
   - Confidence (0-1)
2) "Gap mapping"
   - For each needed capability (A-F), list: covered by which existing skills, and what is still missing.
3) "Adoption plan"
   - Exact install order
   - Validation command per skill
   - Rollback/uninstall command
4) "No-design compliance"
   - Explicitly confirm you did not invent new skills
   - List any items excluded due to weak evidence

Search policy:
- Prefer primary sources (official repo/docs/release pages).
- Prefer recently maintained skills.
- Include at least 8 candidates; if fewer than 8 are truly valid, return fewer and explain why.
- Distinguish Facts vs Inference.
- Include absolute dates (YYYY-MM-DD), not relative words like "recently".

Stop condition:
- If you cannot find enough verified candidates, return the best verified subset and a short list of missing capability areas.
```
