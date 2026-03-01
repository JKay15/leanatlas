import LeanAtlas.Toolbox.FieldTheory.SolvableByRadicals
import Problems.mk_poly_solvability_by_radicals_reuse.Spec

namespace Problems.mk_poly_solvability_by_radicals_reuse

theorem main
    {F : Type} [Field F]
    {E : Type} [Field E] [Algebra F E]
    (α : E) : Goal (F := F) α := by
  intro h
  -- Reuse the promoted toolbox wrapper:
  --   `LeanAtlas.Toolbox.FieldTheory.SolvableByRadicals.isSolvable_gal_of_isSolvableByRad (F:=F) (α:=α) h`
  sorry

end Problems.mk_poly_solvability_by_radicals_reuse
