import LeanAtlas.Toolbox.Queueing.Lindley

namespace Problems.mk_queue_mg1_lindley_reuse_nonneg

/--
A tiny reuse task: after promoting the Lindley recursion to the toolbox,
prove (again) the nonnegativity invariant, but now by *calling the toolbox theorem*.
-/
def Goal : Prop :=
  ∀ (S A : Nat → ℝ) (n : Nat), 0 ≤ LeanAtlas.Toolbox.Queueing.Lindley.W S A n

end Problems.mk_queue_mg1_lindley_reuse_nonneg
