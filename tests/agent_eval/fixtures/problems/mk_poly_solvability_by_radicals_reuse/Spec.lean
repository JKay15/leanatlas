import LeanAtlas.Toolbox.FieldTheory.SolvableByRadicals

namespace Problems.mk_poly_solvability_by_radicals_reuse

open scoped BigOperators

/-!
Reuse task: after promoting a wrapper around `IsSolvableByRad.isSolvable` to the toolbox,
prove the forward implication by calling the toolbox wrapper.
-/
variable {F : Type} [Field F]
variable {E : Type} [Field E] [Algebra F E]
variable (α : E)

def Goal : Prop :=
  IsSolvableByRad F α → IsSolvable (minpoly F α).Gal

end Problems.mk_poly_solvability_by_radicals_reuse
