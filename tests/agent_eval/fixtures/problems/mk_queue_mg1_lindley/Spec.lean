import LeanAtlas.Toolbox.Imports

namespace Problems.mk_queue_mg1_lindley

/--
Lindley recursion (discrete-time form):

`W₀ = 0`, and `W_{n+1} = max 0 (W_n + S_n - A_n)`.

Interpreting:
- `A_n` = inter-arrival time between customer n and n+1
- `S_n` = service time of customer n
- `W_n` = waiting time of customer n

This recurrence underlies the classical analysis of GI/G/1 and M/G/1 queues.
-/
def W (S A : Nat → ℝ) : Nat → ℝ
  | 0 => 0
  | Nat.succ n => max 0 (W S A n + S n - A n)

/-- Basic invariant: waiting times are nonnegative. -/
def Goal (S A : Nat → ℝ) : Prop := ∀ n : Nat, 0 ≤ W S A n

end Problems.mk_queue_mg1_lindley
