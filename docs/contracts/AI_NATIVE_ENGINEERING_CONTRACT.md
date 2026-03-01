# AI_NATIVE_ENGINEERING_CONTRACT v0.1

This contract exists because **vibe coding is fun, but production systems become brittle**.
LeanAtlas principle: Codex may write 99% of the code, but **0% of critical decisions may be left unverified**.

## Terms
- **Vibe coding**: natural-language driven development, biased toward “make it run first”.
- **Verify**: deterministic checks runnable locally/CI (minimum: targeted build/test).
- **Minimal patch**: change the smallest number of files/lines necessary; no drive-by refactors.
- **ExecPlan**: for tasks that are bigger than a tiny patch (>30 minutes, multiple modules, new deps), write an ExecPlan first.

## Non-negotiables

1) **Define scope + verify commands before changing code**
   - Every task must state: which files may change (and which must not), and which commands will verify success.

2) **TDD is the default rhythm**
   - First reduce the problem to a reproducible failing check (a small test, a minimal repro, or a targeted `lake build <target>`).
   - Apply the smallest fix that turns Red → Green.
   - Refactors are allowed only afterwards, and must keep diffs small.

3) **If you can run verification, you must run it**
   - Prefer minimal verification: `lake build <target>` / `lake test` / `lake lint` / `uv run --locked python tests/run.py --profile core`.
   - If you cannot run it (missing env, missing deps), you must write in the report:
     - the exact commands that would be run
     - why they could not be run
     - risks and next steps

4) **Long tasks require an ExecPlan first**
   - If a task crosses phases/subsystems/external deps, write an ExecPlan as defined in `docs/agents/PLANS.md`.

5) **Every external wheel must be pinned + installable + smoke-tested**
   - version pinning: `docs/contracts/THIRD_PARTY_DEPENDENCY_CONTRACT.md`
   - install docs must be executable: `docs/setup/**`
   - smoke tests must exist: `uv run --locked python tests/run.py --profile nightly`

6) **Isolation and rollbackability**
   - background tasks should run in isolated directories/worktrees; must not pollute human work.
   - system-level changes must be PR-shaped (auditable diff, rollbackable).

## LeanAtlas-specific rules
- OPERATOR mode: any PatchScope violation must yield TRIAGED (no “quick platform fix”).
- Every run must emit auditable evidence: AttemptLog / RunReport / RetrievalTrace.
- Every test must be registered in `tests/manifest.json` and appear in `docs/testing/TEST_MATRIX.md`.
