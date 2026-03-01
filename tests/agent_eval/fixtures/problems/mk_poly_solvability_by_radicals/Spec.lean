import LeanAtlas.Toolbox.Imports
import Mathlib.FieldTheory.AbelRuffini

namespace Problems.mk_poly_solvability_by_radicals

open Polynomial

/--
Research-level background: a polynomial is solvable by radicals iff its Galois group is solvable.

Mathlib currently formalizes **one direction** of Abel–Ruffini:

  `IsSolvableByRad F α → IsSolvable (minpoly F α).Gal`.

This fixture starts with an intentionally stronger ("iff") statement to test TRIAGED(BUDGET) vs
a correctly-scoped downgrade (prove the forward direction).
-/
def Goal : Prop :=
  ∀ {F : Type} [Field F] {E : Type} [Field E] [Algebra F E] (α : E),
    IsSolvableByRad F α ↔ IsSolvable (minpoly F α).Gal

end Problems.mk_poly_solvability_by_radicals
