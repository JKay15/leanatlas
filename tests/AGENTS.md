# tests/AGENTS.md — Testing discipline (TDD-first)

This repository uses tests as a contract enforcement mechanism. When you change behavior, you MUST change tests.

## Test tiers
- smoke: fast execution sanity checks
- core: deterministic gates, required for every PR
- nightly: heavy scenarios, stress/soak, optional in CI but required before large merges

## Key commands
- `python tests/run.py --profile core`
- `python tests/e2e/run_cases.py --profile core`
- `python tests/e2e/run_scenarios.py --profile core`
- `python tests/stress/soak.py --iterations 20 --profile core --shuffle --seed 0`

## Critical rule: test-only Toolbox injection must NOT touch the repo
If a test needs a non-empty Toolbox/Incubator, it MUST inject it into the temporary workspace:
- workspace root: `.cache/leanatlas/**`
- never write test-only modules into `LeanAtlas/**` in the real repository
- tests must fail if `git status --porcelain` is not clean after running

## Artifacts and logs
All per-run outputs MUST go under:
- `artifacts/**` and/or `.cache/leanatlas/**`
Both are gitignored. Add new outputs only under those prefixes.
