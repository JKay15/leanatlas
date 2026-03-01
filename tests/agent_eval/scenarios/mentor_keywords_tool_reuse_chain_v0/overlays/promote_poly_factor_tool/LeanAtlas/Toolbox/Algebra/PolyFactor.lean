import Mathlib

namespace LeanAtlas.Toolbox.Algebra.PolyFactor

open Polynomial

/-- A tiny, reusable factorization lemma: `X^2 - 1 = (X - 1)(X + 1)` over any commutative ring. -/
theorem X_sq_sub_one_factor (R : Type) [CommRing R] :
    ((X : Polynomial R)^2 - 1) = (X - 1) * (X + 1) := by
  -- `ring` works for polynomials as a commutative semiring/ ring expression.
  ring

end LeanAtlas.Toolbox.Algebra.PolyFactor
