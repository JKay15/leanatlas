import Mathlib.FieldTheory.AbelRuffini

namespace LeanAtlas.Toolbox.Algebra.AbelRuffiniForward

/--
A convenience wrapper around the mathlib Abel–Ruffini API:

If an element `α` is solvable by radicals over `F`, then the Galois group of its
minimal polynomial is solvable.

Operationally, this is the direction we can actually use as a *tool* inside proofs.
-/
theorem isSolvable_gal_of_isSolvableByRad
    {F : Type} [Field F] {E : Type} [Field E] [Algebra F E] (α : E) :
    IsSolvableByRad F α → IsSolvable (minpoly F α).Gal := by
  intro h
  have hs : IsSolvable (minpoly F (⟨α, h⟩ : solvableByRad F E)).Gal :=
    solvableByRad.isSolvable (F := F) (E := E) ⟨α, h⟩
  rw [show minpoly F (⟨α, h⟩ : solvableByRad F E) = minpoly F α from
    (minpoly.algebraMap_eq (RingHom.injective _) _).symm] at hs
  exact hs

end LeanAtlas.Toolbox.Algebra.AbelRuffiniForward
