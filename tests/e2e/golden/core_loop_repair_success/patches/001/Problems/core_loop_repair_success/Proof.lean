import Problems.core_loop_repair_success.Spec
import Mathlib.Data.Nat.Basic

namespace Problems.core_loop_repair_success

theorem main (a b : Nat) : Goal a b := by
  -- `simpa` expects to close the goal; it will fail without commutativity.
  simpa [Goal, Nat.add_comm]

end Problems.core_loop_repair_success
