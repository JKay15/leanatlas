namespace Problems.smoke_missing_assumption

/-- Problem statement: existence of an element. This is *not* provable without assuming `Nonempty α`. -/
def Statement (α : Type) : Prop := ∃ a : α, True

end Problems.smoke_missing_assumption
