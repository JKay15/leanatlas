import Problems.core_tactic_failure.Spec
import Mathlib.Data.Nat.Basic

namespace Problems.core_tactic_failure

theorem main (a b : Nat) : Goal a b := by
  -- `simpa` expects to close the goal; it will fail without commutativity.
  simpa [Goal]

end Problems.core_tactic_failure
