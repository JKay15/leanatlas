# Mentor keyword classics

This doc explains how we turn the mentor-provided keywords into **representative, checkable, classic theorems** for agent-eval.

Goal:

- Use *known* theorems (so we know the intended answer),
- Keep the Lean goals small enough to be solved repeatedly,
- Exercise the full workflow: retrieval → proof-loop → promotion → reuse → skills/KB mining.

All cited sources are collected (with stable URLs) in:

- `docs/references/mentor_keywords.yaml`

## Keyword → theorem mapping

### Interior point / tangent plane

Representative theorem family:

- Tangent-line inequality for `log` at 1:
  - `ln x ≤ x − 1` for `x > 0`

Why this one:

- It is the “atomic” inequality behind log-barrier lower bounds.
- It is small, deterministic, and formalizes cleanly in Lean.

Tasks:

- `mk_convex_log_barrier` (A-side: prove)
- `mk_convex_log_barrier_gap` (B-side: reuse promoted toolbox lemma)

Primary sources:

- `REF:TOPSOE_LOGBNDS`
- `REF:BV_CVXBOOK_2004`
- `REF:MATHLIB_LOG_BASIC`

### Queueing theory / underlined recurrence / M/G/1

Representative theorem family:

- Lindley recursion (waiting time / workload):
  - `W 0 = 0`
  - `W (n+1) = max 0 (W n + S n − A n)`
- Structural invariant:
  - `0 ≤ W n`

Tasks:

- `mk_queue_mg1_lindley` (A-side: define recursion + prove invariant)
- `mk_queue_mg1_lindley_reuse_nonneg` (B-side: reuse toolbox invariant lemma)

Primary sources:

- `REF:VLASIOU_LINDLEY_THESIS_2006`
- `REF:LEAHU_GG1_2013`

### Little slot / classic conclusion

Representative theorem family:

- Finite-horizon **double counting identity** for occupancy vs. sojourn time:
  - `∑_{t < T} L(t) = ∑_{job j} (number of occupied slots for j)`

This is the combinatorial core behind **Little’s Law** `L = λW`.

Tasks:

- `mk_queue_littles_law_slot` (A-side: build the double-counting lemma)
- `mk_queue_littles_law_slot_reuse` (B-side: reuse the promoted lemma)

Primary sources:

- `REF:LITTLE_OR_1961`
- `REF:LITTLE_50TH_2011`
- `REF:WHITT_ZHANG_PLL_2018`

### Polynomial “solvable”

We deliberately split into two *very different* meanings of “solvable”, because real workflows mix them:

1) **Concrete solvability** (explicit factorization / explicit root)

- Difference-of-squares factorization pattern in `Polynomial`.

Tasks:

- `mk_poly_factorization_square` (A-side: prove factorization)
- `mk_poly_factorization_square_dvd` (B-side: reuse toolbox lemma to derive divisibility)

Primary sources:

- `REF:MATHCENTRE_DIFF_SQUARES_2009`
- `REF:MATHLIB_POLYNOMIAL_BASIC`

2) **Solvability by radicals** (Galois theory / Abel–Ruffini)

- We **do not** force the full iff in v0.
- The v0 pack tests that the agent can:
  - TRIAGE an over-ambitious spec,
  - then solve a downgraded “forward direction” that is covered in mathlib.

Tasks:

- `mk_poly_solvability_by_radicals` (A-side: TRIAGED on full iff, then SUCCESS on downgraded variant)
- `mk_poly_solvability_by_radicals_reuse` (B-side: reuse the promoted lemma)

Primary sources:

- `REF:MATHLIB_ABEL_RUFFINI`
- `REF:DUMMIT_SOLVABILITY_NOTES_2020`
- `REF:RAMOND_ABEL_RUFFINI_2020`

## Traceability rule

- Every task must cite at least **two** `REF:*` entries.
- Every fixture problem must contain a `Sources.md` that uses reference IDs.
- CI checks enforce both.
