import Problems.smoke_missing_assumption.Spec

namespace Problems.smoke_missing_assumption

/-- Main target. This attempt will fail with goal `Nonempty α`. -/
theorem main (α : Type) : Statement α := by
  classical
  refine ⟨Classical.choice ?_, trivial⟩

end Problems.smoke_missing_assumption
