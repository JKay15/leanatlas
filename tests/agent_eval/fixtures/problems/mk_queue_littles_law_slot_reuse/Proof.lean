import LeanAtlas.Toolbox.Queueing.LittleSlot
import Problems.mk_queue_littles_law_slot_reuse.Spec

namespace Problems.mk_queue_littles_law_slot_reuse

theorem main {N T : Nat} : Goal (N := N) (T := T) := by
  intro inSys
  -- Reuse the promoted toolbox theorem:
  --   `LeanAtlas.Toolbox.Queueing.LittleSlot.sum_L_eq_sum_W (N:=_) (T:=_) inSys`
  sorry

end Problems.mk_queue_littles_law_slot_reuse
