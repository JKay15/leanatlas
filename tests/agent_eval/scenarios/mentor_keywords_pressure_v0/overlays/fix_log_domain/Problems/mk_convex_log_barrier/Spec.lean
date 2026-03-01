import LeanAtlas.Toolbox.Imports
import Mathlib.Analysis.SpecialFunctions.Log.Basic

namespace Problems.mk_convex_log_barrier

/--
Classic tangent-line inequality for `log` (a.k.a. log-barrier convexity micro-lemma).

We **must** assume `0 < x` because `Real.log x` is only meaningful as a real function
on the positive reals.

Goal form:

`log x ≤ x - 1` for all `x > 0`.
-/
def Goal : Prop :=
  ∀ x : ℝ, 0 < x → Real.log x ≤ x - 1

end Problems.mk_convex_log_barrier
