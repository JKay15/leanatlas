# User Hard Requirements (Must Follow)

- Explain the meaning of key terms/fields/commands; do not omit semantics.
- Prioritize real workflow tests with Codex in the loop; do not test only helper libraries.
- TDD is mandatory: every phase must provide runnable tests/fixtures/scenarios.
- Do not reinvent the wheel: reuse mature Lean/mathlib/industry approaches first; if custom implementation is needed, state why existing options are insufficient.
- External dependencies must be pinned, documented, and verifiable via smoke checks; drifting versions are forbidden.
- Use uv standard (`pyproject.toml + uv.lock`); do not use `requirements.txt` as source of truth.
- Parallel discussion must follow the Parallel Protocol in this directory (to prevent thread drift and memory loss).
- Skills/automation are cross-cutting: the phase that defines an interface must maintain its related business semantics; Phase5 only owns platform framework and deterministic regeneration.
