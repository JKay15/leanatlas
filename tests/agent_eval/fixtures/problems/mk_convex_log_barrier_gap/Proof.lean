import LeanAtlas.Toolbox.Convex.LogBarrier
import Problems.mk_convex_log_barrier_gap.Spec

namespace Problems.mk_convex_log_barrier_gap

theorem main : Goal := by
  intro x hx
  -- Use the promoted toolbox lemma (tangent-line inequality at 1):
  --   `LeanAtlas.Toolbox.Convex.LogBarrier.log_le_sub_one_of_pos' hx`
  -- Then rearrange the inequality.
  sorry

end Problems.mk_convex_log_barrier_gap
