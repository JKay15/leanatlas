import LeanAtlas.Toolbox.Queueing.Lindley
import Problems.mk_queue_mg1_lindley_reuse_nonneg.Spec

namespace Problems.mk_queue_mg1_lindley_reuse_nonneg

theorem main : Goal := by
  intro S A n
  -- Reuse the promoted lemma:
  --   `LeanAtlas.Toolbox.Queueing.Lindley.W_nonneg S A n`
  sorry

end Problems.mk_queue_mg1_lindley_reuse_nonneg
