import Problems.mk_poly_factorization_square.Spec

namespace Problems.mk_poly_factorization_square

open Polynomial

/-- Main proof entrypoint. -/
theorem main (a : ℝ) : Goal a := by
  -- Expected: `ring` should work, since polynomials form a commutative semiring.
  -- Or use the lemma `sq_sub_sq`.
  sorry

end Problems.mk_poly_factorization_square
