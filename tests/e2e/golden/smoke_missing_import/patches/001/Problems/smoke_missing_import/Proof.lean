import Mathlib.Tactic
import Problems.smoke_missing_import.Spec

namespace Problems.smoke_missing_import

/-- Main target. Fixed by importing `Mathlib.Tactic` to make `linarith` available. -/
theorem main (a b : ℤ) (h : a ≤ b) : Statement a b h := by
  simpa [Statement] using add_le_add_right h 1

end Problems.smoke_missing_import
