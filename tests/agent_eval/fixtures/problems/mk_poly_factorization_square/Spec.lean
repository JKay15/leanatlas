import LeanAtlas.Toolbox.Imports

namespace Problems.mk_poly_factorization_square

open Polynomial

/--
A minimal “polynomial is solvable” micro-task: if a constant `a` is a square, then
`X^2 - a^2` factors as `(X - a)(X + a)`.

This is deliberately chosen because it is classical and should be easy for an agent to discharge,
while still exercising the polynomial API.
-/
def Goal (a : ℝ) : Prop :=
  (X : Polynomial ℝ)^2 - C (a^2) = (X - C a) * (X + C a)

end Problems.mk_poly_factorization_square
