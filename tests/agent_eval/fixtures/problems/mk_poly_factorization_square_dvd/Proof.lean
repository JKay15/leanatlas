import LeanAtlas.Toolbox.Polynomial.Factorization
import Problems.mk_poly_factorization_square_dvd.Spec

namespace Problems.mk_poly_factorization_square_dvd

open Polynomial

theorem main : Goal := by
  intro a
  -- Use the promoted toolbox factorization:
  --   `LeanAtlas.Toolbox.Polynomial.Factorization.X_sq_sub_C_sq a`
  -- Then rewrite and conclude `(X - C a) ∣ (X - C a) * (X + C a)`.
  sorry

end Problems.mk_poly_factorization_square_dvd
