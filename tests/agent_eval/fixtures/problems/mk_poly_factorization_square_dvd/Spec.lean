import LeanAtlas.Toolbox.Polynomial.Factorization

namespace Problems.mk_poly_factorization_square_dvd

open Polynomial

/--
Reuse task: after promoting the difference-of-squares factorization to the toolbox,
prove a simple divisibility corollary.
-/
def Goal : Prop :=
  ∀ a : ℝ,
    (X - C a : Polynomial ℝ) ∣ ((X : Polynomial ℝ) ^ 2 - C (a ^ 2))

end Problems.mk_poly_factorization_square_dvd
