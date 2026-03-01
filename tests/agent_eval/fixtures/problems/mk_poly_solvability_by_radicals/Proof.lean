import Problems.mk_poly_solvability_by_radicals.Spec

namespace Problems.mk_poly_solvability_by_radicals

open Polynomial

/-- Main proof entrypoint. -/
theorem main : Goal := by
  intro F _ E _ _ α
  -- v0: likely TRIAGED(BUDGET) because the reverse direction is not available in mathlib.
  -- v1: expected downgrade to the forward direction and then:
  --   `intro hα`
  --   `have hs : IsSolvable (minpoly F (⟨α, hα⟩ : solvableByRad F E)).Gal :=`
  --   `  solvableByRad.isSolvable (F := F) (E := E) ⟨α, hα⟩`
  --   `rw [show minpoly F (⟨α, hα⟩ : solvableByRad F E) = minpoly F α from`
  --   `  (minpoly.algebraMap_eq (RingHom.injective _) _).symm] at hs`
  --   `exact hs`
  sorry

end Problems.mk_poly_solvability_by_radicals
