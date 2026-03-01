# Stress / Soak tests (manual)

These tests are **not** part of core CI. They are intended to be run locally (or in a dedicated nightly CI runner) with Lean/Lake installed.

## Soak runner

Runs many golden cases back-to-back inside the *same* workspace to expose:
- state leaks across cases
- regressions introduced by sequential edits
- flakiness across repetitions
- rough performance drift (very coarse)

Example:

```bash
python tests/stress/soak.py --iterations 10 --profile core --shuffle --seed 0
```

