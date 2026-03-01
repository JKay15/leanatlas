/-
LeanAtlas Toolbox (fixture): Polynomial factorization pattern (difference of squares).

Source anchors (see `docs/references/mentor_keywords.yaml`):
- `MATHCENTRE_DIFF_SQUARES_2009` — a^2 − b^2 = (a − b)(a + b)
- `MATHLIB_POLYNOMIAL_BASIC` — Lean `Polynomial` primitives (X, C, multiplication)

This file is introduced by an **agent-eval overlay** to simulate promotion + reuse.
-/

import Mathlib

namespace LeanAtlas.Toolbox.Polynomial.Factorization

/--
A handy algebraic factorization in `Polynomial ℝ`:

`X^2 - C(a^2) = (X - C a) * (X + C a)`.

We prove it by rewriting to `sq_sub_sq` (difference of squares) in a commutative ring.
-/
theorem X_sq_sub_C_sq (a : ℝ) :
    (_root_.Polynomial.X : _root_.Polynomial ℝ) ^ 2 - _root_.Polynomial.C (a ^ 2) =
      (_root_.Polynomial.X - _root_.Polynomial.C a) * (_root_.Polynomial.X + _root_.Polynomial.C a) := by
  -- `sq_sub_sq` gives `(X^2 - (C a)^2) = (X + C a) * (X - C a)`.
  -- Then simp rewrites `(C a)^2` to `C(a^2)`, and commutativity swaps the factors.
  have h :
      (_root_.Polynomial.X : _root_.Polynomial ℝ) ^ 2 - _root_.Polynomial.C (a ^ 2) =
        (_root_.Polynomial.X + _root_.Polynomial.C a) * (_root_.Polynomial.X - _root_.Polynomial.C a) := by
    simpa using
      (sq_sub_sq (_root_.Polynomial.X : _root_.Polynomial ℝ) (_root_.Polynomial.C a))
  simpa [mul_comm, mul_left_comm, mul_assoc] using h

end LeanAtlas.Toolbox.Polynomial.Factorization
