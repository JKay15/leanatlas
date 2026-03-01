-- Scratch.lean for mk_queue_mg1_lindley

-- You may use `sorry` here. Never import Scratch from Proof/Cache.

import Problems.mk_queue_mg1_lindley.Spec

namespace Problems.mk_queue_mg1_lindley

-- Example: the max lower bound lemma is immediate.
theorem scratch_nonneg_of_max (x : ℝ) : 0 ≤ max 0 x := by
  simpa using le_max_left 0 x

end Problems.mk_queue_mg1_lindley
