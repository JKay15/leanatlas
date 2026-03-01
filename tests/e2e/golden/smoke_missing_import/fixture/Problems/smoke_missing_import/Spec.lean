import Mathlib.Data.Int.Basic

namespace Problems.smoke_missing_import

/-- Problem statement: a simple monotonicity lemma. -/
def Statement (a b : ℤ) (h : a ≤ b) : Prop := a + 1 ≤ b + 1

end Problems.smoke_missing_import
