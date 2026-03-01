import Mathlib.Data.Finset.Card
import Mathlib.Data.Finset.Filter
import Mathlib.Data.Fintype.Basic
import Mathlib.Algebra.BigOperators.Group.Finset.Basic

namespace LeanAtlas.Toolbox.Queueing.LittleSlot

open scoped BigOperators

/-- Occupancy at time `t` (number of customers in system at slot `t`). -/
def L {N T : Nat} (inSys : Fin N → Fin T → Bool) (t : Fin T) : Nat :=
  (Finset.univ.filter (fun i : Fin N => inSys i t)).card

/-- Sojourn time (in slots) for customer `i`. -/
def W {N T : Nat} (inSys : Fin N → Fin T → Bool) (i : Fin N) : Nat :=
  (Finset.univ.filter (fun t : Fin T => inSys i t)).card

/--
Double-counting identity underlying Little's law:

`∑_t L(t) = ∑_i W(i)`.

This is purely a finite combinatorial fact about a 0/1 indicator matrix.
-/
theorem sum_L_eq_sum_W {N T : Nat} (inSys : Fin N → Fin T → Bool) :
    (∑ t : Fin T, L inSys t) = (∑ i : Fin N, W inSys i) := by
  classical
  -- Turn both sides into a double sum of indicators, then swap order.
  calc
    (∑ t : Fin T, L inSys t)
        = ∑ t : Fin T, ∑ i : Fin N, if inSys i t then (1 : Nat) else 0 := by
            simp [L, Finset.card_eq_sum_ones, Finset.sum_filter]
    _ = ∑ i : Fin N, ∑ t : Fin T, if inSys i t then (1 : Nat) else 0 := by
            -- swap the two (finite) sums
            simpa [Finset.sum_comm]
    _ = (∑ i : Fin N, W inSys i) := by
            simp [W, Finset.card_eq_sum_ones, Finset.sum_filter]

end LeanAtlas.Toolbox.Queueing.LittleSlot
