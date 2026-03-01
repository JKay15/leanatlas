# Phase6 — Mentor Keywords: Classic Conclusions and Traceable Sources

Goal: map instructor keywords to representative classic conclusions that are **verifiable, traceable, and formalizable**.

- **Traceable**: each conclusion includes reliable sources (book/paper/official docs) and Lean entrypoints (module/lemma).
- **Verifiable**: references align definitions/assumptions during natural-language planning and reduce guesswork.
- **Reusable**: Lean formalizations should be deposited into Toolbox (fixture/test context) and counted in scenario-level tool-reuse signals.

Task-level `references:` should include:
1. the corresponding local entry in this file,
2. at least one external authoritative source (URL/DOI page),
3. at least one mathlib/Lean official documentation page when directly relying on mathlib lemmas.

---

## 1) Keyword -> classic conclusion -> task/tool mapping

| Tutor keywords | Representative conclusion (informal) | Task IDs | Toolbox deposition target |
|---|---|---|---|
| interior point / tangent plane | Log tangent inequality: for `x > 0`, `log x <= x - 1` | `mk_convex_log_barrier`, `mk_convex_log_barrier_gap` | `LeanAtlas.Toolbox.Convex.LogBarrier` (`log_le_sub_one`) |
| queueing (Lindley recursion / M/G/1) | Lindley recursion: `W_{n+1} = max(0, W_n + S_n - A_n)` and nonnegativity | `mk_queue_mg1_lindley` | `LeanAtlas.Toolbox.Queueing.Lindley` (`step`, `nonneg`) |
| Little's law (slot model) | sample-path double counting: total occupancy sum = total sojourn sum | `mk_queue_littles_law_slot` | `LeanAtlas.Toolbox.Queueing.LittleSlot` (`sum_occupancy_eq_sum_sojourn`) |
| solvability by radicals | representative Abel–Ruffini direction: solvable by radicals implies solvable Galois group | `mk_poly_solvability_by_radicals` | `LeanAtlas.Toolbox.FieldTheory.SolvableByRadicals` |
| factorization identity | difference-of-squares identity: `a^2 - b^2 = (a+b)(a-b)` | `mk_poly_factorization_square`, `mk_poly_factorization_square_dvd` | `LeanAtlas.Toolbox.Polynomial.Factorization` |

---

## 2) Itemized references

### 2.1 Log tangent inequality

Conclusion:
- For `x > 0`, `log x <= x - 1`; equality at `x = 1`.

Lean mapping:
- mathlib: `Real.log_le_sub_one_of_pos`
- Toolbox wrapper: `LeanAtlas.Toolbox.Convex.LogBarrier.log_le_sub_one`

References:
- Boyd & Vandenberghe, *Convex Optimization*:
  - https://web.stanford.edu/~boyd/cvxbook/bv_cvxbook.pdf
- mathlib docs (`Mathlib.Analysis.SpecialFunctions.Log.Basic`):
  - https://leanprover-community.github.io/mathlib4_docs/Mathlib/Analysis/SpecialFunctions/Log/Basic.html

### 2.2 Lindley recursion

Conclusion:
- `W_{n+1} = max(0, W_n + S_n - A_n)`.

Lean mapping:
- `LeanAtlas.Toolbox.Queueing.Lindley`

References:
- Lindley (1952):
  - https://www.cambridge.org/core/journals/proceedings-of-the-cambridge-philosophical-society/article/the-theory-of-queues-with-a-single-server/AA82531435D96C9592F268E87A8A404F
- Asmussen (Applied Probability and Queues):
  - https://books.google.com.na/books?id=c4_xBwAAQBAJ

### 2.3 Little's law (slot/sample-path form)

Conclusion:
- `L = lambda * W`; in formalization, start from finite-window sample-path double counting.

Lean mapping:
- `LeanAtlas.Toolbox.Queueing.LittleSlot.sum_occupancy_eq_sum_sojourn`

References:
- Little (1961):
  - https://scispace.com/papers/a-proof-for-the-queuing-formula-l-w-3bokd0t11t
- Whitt notes:
  - https://www.columbia.edu/~ww2040/LittleLaw.pdf

### 2.4 Solvability by radicals / Abel–Ruffini direction

Conclusion:
- Representative direction for Phase6: solvable by radicals -> solvable Galois group.

Lean mapping:
- mathlib: `Mathlib.FieldTheory.AbelRuffini`
- Toolbox wrapper: `LeanAtlas.Toolbox.FieldTheory.SolvableByRadicals.solvable_of_solvableByRad`

References:
- mathlib docs:
  - https://leanprover-community.github.io/mathlib4_docs/Mathlib/FieldTheory/AbelRuffini.html

### 2.5 Difference of squares

Conclusion:
- `a^2 - b^2 = (a+b)(a-b)`.

Lean mapping:
- mathlib lemma: `sq_sub_sq`
- Toolbox wrapper: `LeanAtlas.Toolbox.Polynomial.Factorization.sq_sub_sq_factor`

References:
- mathlib docs:
  - https://leanprover-community.github.io/mathlib4_docs/Mathlib/Algebra/Ring/Commute.html
