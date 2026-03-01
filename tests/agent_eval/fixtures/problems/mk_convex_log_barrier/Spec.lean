import LeanAtlas.Toolbox.Imports
import Mathlib.Analysis.SpecialFunctions.Log.Basic

namespace Problems.mk_convex_log_barrier

/--
A classical inequality used as the core of a log-barrier / interior-point analysis:

  `log x ≤ x - 1`.

Important: in reality this only holds for `x > 0`.

This fixture starts *without* the domain assumption to force a clean TRIAGE (v0),
then a corrected version should add the missing assumption and succeed (v1).
-/
def Goal : Prop := ∀ x : ℝ, Real.log x ≤ x - 1

end Problems.mk_convex_log_barrier
