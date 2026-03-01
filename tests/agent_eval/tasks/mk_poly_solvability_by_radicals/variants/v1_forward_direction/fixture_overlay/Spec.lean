import LeanAtlas.Toolbox.Imports
import Mathlib.FieldTheory.AbelRuffini

namespace Problems.mk_poly_solvability_by_radicals

open scoped Classical

/-- v1 (downgraded): forward direction of a standard Abel–Ruffini consequence.

This is intentionally aligned with the mathlib lemma `solvableByRad.isSolvable`.
-/
def Goal : Prop :=
  ∀ (F : Type) [Field F]
    (E : Type) [Field E] [Algebra F E]
    (α : E),
      IsSolvableByRad F α → IsSolvable (minpoly F α).Gal

end Problems.mk_poly_solvability_by_radicals
