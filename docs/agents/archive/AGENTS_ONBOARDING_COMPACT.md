On first prompt in a fresh clone (missing `.cache/leanatlas/onboarding/state.json`),
run `.agents/skills/leanatlas-onboard/SKILL.md` and `docs/agents/ONBOARDING.md` before any normal reply.

Hard trigger rule:
- This applies to any first user message, including greetings like `hi`.
- Do not reply with a generic question before onboarding routing.
- First response must be: banner + A/B/C consent menu.

The full long-form onboarding block is archived at:
- `docs/agents/archive/AGENTS_ONBOARDING_VERBOSE.md`

After `bootstrap` + `doctor` both pass, root `AGENTS.md` must stay compact.
Do not re-expand this block in `AGENTS.md`.
