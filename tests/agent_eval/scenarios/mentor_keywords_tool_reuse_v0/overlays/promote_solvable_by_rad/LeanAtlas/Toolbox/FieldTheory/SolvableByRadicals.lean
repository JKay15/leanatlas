/-
LeanAtlas Toolbox (fixture): Solvable-by-radicals / Abel–Ruffini bridge.

Source anchors (see `docs/references/mentor_keywords.yaml`):
- `MATHLIB_ABEL_RUFFINI` — Lean formal statement used here
- `DUMMIT_SOLVABILITY_NOTES_2020` — Galois theory exposition (solvability in radicals)
- `RAMOND_ABEL_RUFFINI_2020` — readable Abel–Ruffini proof sketch

This file is introduced by an **agent-eval overlay** to simulate promotion + reuse.
-/

import Mathlib.FieldTheory.AbelRuffini

namespace LeanAtlas.Toolbox.FieldTheory.SolvableByRadicals

/--
A small wrapper around the mathlib lemma `IsSolvableByRad.isSolvable`:

If an element `α` is solvable by radicals over `F`, then the Galois group of its minimal
polynomial is solvable.

This is the forward implication that is routinely reused in many “solvable by radicals” tasks.
-/
theorem isSolvable_gal_of_isSolvableByRad
    {F : Type} [Field F]
    {E : Type} [Field E] [Algebra F E]
    {α : E} :
    IsSolvableByRad F α → IsSolvable (minpoly F α).Gal := by
  intro h
  have hs : IsSolvable (minpoly F (⟨α, h⟩ : solvableByRad F E)).Gal :=
    solvableByRad.isSolvable (F := F) (E := E) ⟨α, h⟩
  rw [show minpoly F (⟨α, h⟩ : solvableByRad F E) = minpoly F α from
    (minpoly.algebraMap_eq (RingHom.injective _) _).symm] at hs
  exact hs

end LeanAtlas.Toolbox.FieldTheory.SolvableByRadicals
