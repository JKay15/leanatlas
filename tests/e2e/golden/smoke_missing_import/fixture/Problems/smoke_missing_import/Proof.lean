import Problems.smoke_missing_import.Spec

namespace Problems.smoke_missing_import

/-- Main target. Intentionally uses `linarith` without importing `Mathlib.Tactic`. -/
theorem main (a b : ℤ) (h : a ≤ b) : Statement a b h := by
  linarith

end Problems.smoke_missing_import
