/-
LeanAtlas Toolbox (fixture): Lindley recursion (queueing waiting-time/workload recursion).

Source anchors (see `docs/references/mentor_keywords.yaml`):
- `VLASIOU_LINDLEY_THESIS_2006` — thesis with a dedicated section on Lindley’s recursion
- `LEAHU_GG1_2013` — paper stating the classical recursion for G/G/1 waiting times

This file is introduced by an **agent-eval overlay** to simulate promotion + reuse.
-/

import Mathlib

namespace LeanAtlas.Toolbox.Queueing.Lindley

/--
Lindley recursion (GI/GI/1 waiting-time process):

* `W 0 = 0`
* `W (n+1) = max 0 (W n + S n - A n)`

This file keeps the recursion purely deterministic (no probabilistic assumptions).
-/
def W (S A : Nat → ℝ) : Nat → ℝ
  | 0 => 0
  | n + 1 => max 0 (W S A n + S n - A n)

/-- Structural invariant: `W S A n ≥ 0` for all `n`. -/
theorem W_nonneg (S A : Nat → ℝ) : ∀ n : Nat, 0 ≤ W S A n := by
  intro n
  cases n with
  | zero =>
      simp [W]
  | succ n =>
      -- `0 ≤ max 0 _` holds without any further assumptions.
      simpa [W] using (le_max_left (0 : ℝ) (W S A n + S n - A n))

end LeanAtlas.Toolbox.Queueing.Lindley
