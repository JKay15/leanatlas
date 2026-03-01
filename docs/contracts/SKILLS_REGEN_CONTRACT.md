# SKILLS_REGEN_CONTRACT v0

Purpose: define deterministic regeneration of:
- Skills routing docs under `.agents/skills/_generated/**`
- Skills index and related metadata

This contract exists to prevent “skills drift”:
- library evolves (Toolbox/Incubator), but skills stay stale → Codex keeps reinventing wheels.

## 1) Single source of truth

- Generator script: `tools/coordination/skills_regen.py`
- Stub generator (optional): `tools/coordination/skills_stubgen.py`

## 2) Inputs (V0)

- `LeanAtlas/Toolbox/**` module surface
- `LeanAtlas/Incubator/Seeds/**` surface (optional)
- `tools/index/*` metadata (gc_state, promotions, dedup info)
- any curated templates under `.agents/skills/templates/**`

V0 must not require an LLM.

## 3) Outputs (V0)

- `.agents/skills/_generated/**`
  - per-skill `SKILL.md`
  - optional `routing.json` / `index.json`

Rules:
- Generated files must be clearly marked as generated.
- Generated files must be deterministic:
  - same input repo state ⇒ byte-identical outputs (or canonical JSON stable outputs).

## 4) Change discipline

- Any manual edits to generated files are forbidden.
- Edits must be applied to source templates or generator logic.

## 5) TDD requirements

Core profile must cover:
- generator runs without external deps (no MCP required)
- outputs are deterministic on the same inputs
- generated SKILL.md files satisfy the Skill shape contract (Use when / Don’t use when / Outputs / Must-run checks)
- `docs/testing/TEST_MATRIX.md` is updated if the manifest changes

Nightly profile may include:
- real library surface extraction (requires Lean env)
- larger regeneration runs (performance)
