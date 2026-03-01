# tests/e2e

This folder contains **deterministic golden cases** for the small-loop.

- `golden/<case_id>/case.yaml` defines expected outcomes and coverage tags.
- Validation (core): `python tests/e2e/validate_cases.py`

A real runner that executes cases (copy fixture -> run loop -> compare outputs)
is added in later phases.


Run core executable cases (requires local Lean/Lake + mathlib build):

  python tests/e2e/run_cases.py --profile core
