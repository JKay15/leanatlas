# Mentor Keywords: Classic Theorems and Traceable Sources (Phase6 taskpack)

Purpose: map instructor keywords to **verifiable and citable** classic conclusions, and pin references in task definitions to avoid unverifiable discussion.

References here are human-traceable authoritative sources.
Lean correctness still uses `mathlib + local compilation` as the source of truth.

---

## 1) Convex optimization / interior point / tangent plane

### Classic conclusion

- Log tangent inequality:

\[
\log x \le x - 1 \quad (x > 0)
\]

Equivalent gap form:

\[
0 \le x - 1 - \log x \quad (x > 0)
\]

### References

- Boyd & Vandenberghe, *Convex Optimization*:
  - https://web.stanford.edu/~boyd/cvxbook/bv_cvxbook.pdf

### Related tasks

- `mk_convex_log_barrier`
- `mk_convex_log_barrier_gap`

---

## 2) Queueing / Lindley recursion / M/G/1 kernel

### Classic conclusion

- Lindley recursion (waiting-time/workload form):

\[
W_{n+1} = \max\{0,\; W_n + B_n - A_n\}
\]

### References

- Adan & Resing, *Queueing Systems* (Lindley section):
  - https://iadan.win.tue.nl/queueing.pdf

### Related tasks

- `mk_queue_mg1_lindley`
- `mk_queue_mg1_lindley_reuse_nonneg`

---

## 3) Queueing / Little's law / slot-level sample path

### Classic conclusion

- Little's law:

\[
L = \lambda W
\]

For Lean tasks, we formalize a finite-window double-counting identity first.

### References

- Little (1961), *Operations Research*:
  - https://pubsonline.informs.org/doi/pdf/10.1287/opre.9.3.383
- Whitt, retrospective notes:
  - https://people.cs.umass.edu/~emery/classes/cmpsci691st/readings/OS/Littles-Law-50-Years-Later.pdf
- Adan & Resing notes:
  - https://iadan.win.tue.nl/queueing.pdf

### Related tasks

- `mk_queue_littles_law_slot`
- `mk_queue_littles_law_slot_reuse`

---

## 4) Algebra / explicit polynomial solvability facts

### Classic conclusion

- Difference-of-squares factorization:

\[
X^2 - Y^2 = (X+Y)(X-Y)
\]

### References

- Keith Conrad, *Universal identities*:
  - https://kconrad.math.uconn.edu/blurbs/ugrad/univid.pdf

### Related tasks

- `mk_poly_factorization_square`
- `mk_poly_factorization_square_dvd`

---

## 5) Field theory / solvable by radicals / Abel–Ruffini

### Classic conclusion

- Standard criterion links solvability by radicals with solvability of the Galois group.
- Abel–Ruffini: general quintics are not solvable by radicals.

### References

- Dummit notes, *Solvability in radicals*:
  - https://www.math.neu.edu/~dummit/docs/solvability_in_radicals.pdf

### Related tasks

- `mk_poly_solvability_by_radicals`
- `mk_poly_solvability_by_radicals_reuse`
