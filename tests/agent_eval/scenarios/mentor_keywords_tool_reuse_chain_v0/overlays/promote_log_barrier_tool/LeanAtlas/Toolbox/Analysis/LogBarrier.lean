import Mathlib.Analysis.SpecialFunctions.Log.Basic

namespace LeanAtlas.Toolbox.Analysis.LogBarrier

/--
Tangent-line inequality for `Real.log` at `1`.

This is a classic micro-lemma used in interior-point methods (log barrier) and in
"tangent plane" style inequalities:

`log x ≤ x - 1` for all `x > 0`.

We intentionally expose a stable wrapper name so downstream proofs can avoid
re-discovering the right mathlib lemma name.
-/
theorem log_le_sub_one_of_pos {x : ℝ} (hx : 0 < x) : Real.log x ≤ x - 1 := by
  simpa using Real.log_le_sub_one_of_pos hx

end LeanAtlas.Toolbox.Analysis.LogBarrier
