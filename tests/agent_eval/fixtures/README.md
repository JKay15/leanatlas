# Agent-eval fixtures

These fixtures are **templates** used by Phase6 agent-eval runners.

Key rules:
- Fixtures live under `tests/agent_eval/fixtures/**` so they are **not** part of the main Lean library build.
- A runner copies a fixture into a fresh workspace under `Problems/<problem_slug>/`.
- Fixtures may start incomplete (e.g. `Proof.lean` contains `sorry`) because the agent is expected to complete them.
- After a run succeeds, the resulting workspace artifacts are stored under `artifacts/agent_evals/**` (gitignored).

The fixture directory for a problem slug MUST contain at least:
- `Spec.lean` (problem statement / definitions; should be stable)
- `Proof.lean` (main proof file; agent edits here)
- `Cache.lean` and optional `Cache/**.lean` (intermediate lemmas; agent edits here)
- `Scratch.lean` (agent may use `sorry`; MUST NOT be imported by Proof/Cache)
- `Tasks.yaml` (domain hints; optional but recommended)
