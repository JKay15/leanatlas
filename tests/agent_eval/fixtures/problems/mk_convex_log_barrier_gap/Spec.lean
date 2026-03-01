import Mathlib.Analysis.SpecialFunctions.Log.Basic

-- NOTE: This problem is designed to run *after* a tool-promotion overlay introduces
-- `LeanAtlas.Toolbox.Convex.LogBarrier`.
-- In the tool-reuse scenario, that module is added to the workspace between tasks.
import LeanAtlas.Toolbox.Convex.LogBarrier

namespace Problems.mk_convex_log_barrier_gap

/--
Interior-point / tangent-line inequality as a nonnegativity statement:

`x - 1 - log x ≥ 0` for `0 < x`.

(Equivalently `log x ≤ x - 1`.)
-/
def Goal : Prop := ∀ x : ℝ, 0 < x → 0 ≤ x - 1 - Real.log x

end Problems.mk_convex_log_barrier_gap
