import Mathlib

namespace LeanAtlas.Toolbox.Queueing.Lindley

/--
Lindley recursion (waiting-time recursion) for a G/G/1 (including M/G/1) queue.

This is the standard "underline recurrence":

`W 0 = 0`
`W (n+1) = max 0 (W n + S n - A n)`

where `S n` is service time and `A n` is inter-arrival time.
-/
def W (S A : Nat → ℝ) : Nat → ℝ
  | 0 => 0
  | Nat.succ n => max 0 (W S A n + S n - A n)

@[simp] theorem W_zero (S A : Nat → ℝ) : W S A 0 = 0 := by
  rfl

@[simp] theorem W_succ (S A : Nat → ℝ) (n : Nat) : W S A (Nat.succ n) = max 0 (W S A n + S n - A n) := by
  rfl

/-- `W n` is always nonnegative (trivial from the `max 0 _` form). -/
theorem W_nonneg (S A : Nat → ℝ) : ∀ n, 0 ≤ W S A n
  | 0 => by
      simp [W]
  | Nat.succ n => by
      -- `0 ≤ max 0 _`
      simpa [W] using (le_max_left (0 : ℝ) (W S A n + S n - A n))

end LeanAtlas.Toolbox.Queueing.Lindley
