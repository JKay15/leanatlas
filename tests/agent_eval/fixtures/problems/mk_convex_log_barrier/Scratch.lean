-- Scratch.lean for mk_convex_log_barrier

-- You may use `sorry` here. Never import Scratch from Proof/Cache.

import Problems.mk_convex_log_barrier.Spec

namespace Problems.mk_convex_log_barrier

-- Example: with the right assumption, mathlib already has the lemma.
theorem scratch_with_pos (x : ℝ) (hx : 0 < x) : Real.log x ≤ x - 1 := by
  simpa using Real.log_le_sub_one_of_pos hx

end Problems.mk_convex_log_barrier
