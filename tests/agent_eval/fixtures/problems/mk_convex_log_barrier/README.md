# mk_convex_log_barrier (fixture)

This fixture is meant to represent a realistic *convex optimization / interior-point* micro-task:

- A log-barrier analysis typically relies on convexity/concavity properties of `log` and the standard inequality
  `log x ≤ x - 1` (for `x > 0`).

The fixture intentionally omits the domain assumption in `Goal` so that:
- Variant v0 should **TRIAGE** as an assumption/statement issue.
- Variant v1 is expected to patch the statement (add `0 < x`) and then prove it via `Real.log_le_sub_one_of_pos`.
