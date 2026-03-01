import LeanAtlas.Toolbox.Imports
import Mathlib.Data.Finset.Basic
import Mathlib.Data.Finset.Card
import Mathlib.Data.Fintype.Basic

namespace Problems.mk_queue_littles_law_slot

open scoped BigOperators

/-!
A discrete-time “slot” identity that underlies Little's law:

Let `inSys i t` mean customer `i` is in the system at time-slot `t`.
Define:
- `L(t)` = number of customers in the system at time `t`
- `W(i)` = number of time-slots customer `i` spends in the system

Then double-counting the indicator matrix implies:

  `∑_t L(t) = ∑_i W(i)`.

This is the cleanest formal kernel for the sample-path proof of Little's law.
-/
variable {N T : Nat}

/-- Occupancy at time `t`. -/
def L (inSys : Fin N → Fin T → Bool) (t : Fin T) : Nat :=
  -- `Finset.filter` expects a predicate `α → Prop`, so we lift the Bool to a Prop via `= true`.
  (Finset.univ.filter (fun i : Fin N => inSys i t = true)).card

/-- Sojourn time (in slots) for customer `i`. -/
def W (inSys : Fin N → Fin T → Bool) (i : Fin N) : Nat :=
  (Finset.univ.filter (fun t : Fin T => inSys i t = true)).card

/-- The double-counting identity. -/
def Goal (inSys : Fin N → Fin T → Bool) : Prop :=
  (∑ t : Fin T, L inSys t) = (∑ i : Fin N, W inSys i)

end Problems.mk_queue_littles_law_slot
