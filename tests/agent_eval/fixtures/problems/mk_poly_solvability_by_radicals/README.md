# mk_poly_solvability_by_radicals (fixture)

This is a deliberately *scope-sensitive* fixture:

- The “full iff” criterion is classic but **too large** for most proof loops.
- Mathlib already contains one direction (Abel–Ruffini: solvable-by-radicals ⇒ solvable Galois group).

So this problem is designed to test:
1) Can the agent recognize an oversized goal and TRIAGE cleanly?
2) Can the agent *downgrade* to a provable, high-value sub-goal using existing library facts?
