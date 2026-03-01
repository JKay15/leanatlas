import LeanAtlas.Toolbox.Imports
import Mathlib.FieldTheory.AbelRuffini

namespace Problems.mk_poly_solvability_by_radicals

open Polynomial

/--
Downgraded (provable) direction of Abel–Ruffini available in mathlib:

`IsSolvableByRad F α → IsSolvable (minpoly F α).Gal`.

The reverse direction (⇐) is research-level and not assumed available.
-/
def Goal : Prop :=
  ∀ {F : Type} [Field F] {E : Type} [Field E] [Algebra F E] (α : E),
    IsSolvableByRad F α → IsSolvable (minpoly F α).Gal

end Problems.mk_poly_solvability_by_radicals
