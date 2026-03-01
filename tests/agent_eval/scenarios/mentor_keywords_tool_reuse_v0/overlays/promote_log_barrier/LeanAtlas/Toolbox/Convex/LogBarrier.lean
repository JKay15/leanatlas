/-
LeanAtlas Toolbox (fixture): Log-barrier inequality.

Mathematical source anchors (see `docs/references/mentor_keywords.yaml`):
- `TOPSOE_LOGBNDS` — basic inequality: ln x ≤ x − 1 for x > 0
- `BV_CVXBOOK_2004` — barrier / interior-point method context for log barriers
- `MATHLIB_LOG_BASIC` — Lean lemma names/types (e.g. `Real.log_le_sub_one_of_pos`)

This file is introduced by an **agent-eval overlay** to simulate promotion + reuse.
-/

import Mathlib.Analysis.SpecialFunctions.Log.Basic

namespace LeanAtlas.Toolbox.Convex.LogBarrier

/--
Tangent line inequality for `Real.log` at `x = 1`:

`log x ≤ x - 1` for `0 < x`.

This is the classic inequality behind the log-barrier lower bound in interior-point methods.
-/
theorem log_le_sub_one_of_pos' {x : ℝ} (hx : 0 < x) :
    Real.log x ≤ x - 1 := by
  simpa using Real.log_le_sub_one_of_pos hx

end LeanAtlas.Toolbox.Convex.LogBarrier
