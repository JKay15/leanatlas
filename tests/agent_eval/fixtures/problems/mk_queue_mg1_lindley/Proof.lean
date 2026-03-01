import Problems.mk_queue_mg1_lindley.Spec

namespace Problems.mk_queue_mg1_lindley

/-- Main proof entrypoint. -/
theorem main (S A : Nat → ℝ) : Goal S A := by
  intro n
  -- Stable skeleton:
  -- `induction n with`
  -- `| zero => simp [W]`
  -- `| succ n ih =>`
  -- `    simpa [W] using`
  -- `      (le_max_left (0 : ℝ) (W S A n + S n - A n))`
  sorry

end Problems.mk_queue_mg1_lindley
