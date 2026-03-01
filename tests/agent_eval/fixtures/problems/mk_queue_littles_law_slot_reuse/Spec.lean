import LeanAtlas.Toolbox.Queueing.LittleSlot

namespace Problems.mk_queue_littles_law_slot_reuse

open scoped BigOperators

variable {N T : Nat}

/--
Reuse task: after promoting the “double counting” identity to the toolbox,
prove the same identity by calling the toolbox theorem.
-/
def Goal : Prop :=
  ∀ (inSys : Fin N → Fin T → Bool),
    (∑ t : Fin T, LeanAtlas.Toolbox.Queueing.LittleSlot.L (N:=N) (T:=T) inSys t) =
      (∑ i : Fin N, LeanAtlas.Toolbox.Queueing.LittleSlot.W (N:=N) (T:=T) inSys i)

end Problems.mk_queue_littles_law_slot_reuse
