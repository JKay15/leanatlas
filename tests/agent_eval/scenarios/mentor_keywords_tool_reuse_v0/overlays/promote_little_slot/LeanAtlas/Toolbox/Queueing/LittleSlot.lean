/-
LeanAtlas Toolbox (fixture): Little’s Law — time-slot / sample-path double counting core.

Source anchors (see `docs/references/mentor_keywords.yaml`):
- `LITTLE_OR_1961` — original statement/proof of L = λW
- `LITTLE_50TH_2011` — 50th anniversary overview + sample-path framing
- `WHITT_ZHANG_PLL_2018` — periodic/discrete-time-friendly variants

This file is introduced by an **agent-eval overlay** to simulate promotion + reuse.
-/

import Mathlib

namespace LeanAtlas.Toolbox.Queueing.LittleSlot

open scoped BigOperators

variable {N T : Nat}

/-- Occupancy in slot `t`: number of customers in the system at time `t`. -/
def L (inSys : Fin N → Fin T → Bool) (t : Fin T) : Nat :=
  (Finset.univ.filter (fun i : Fin N => inSys i t = true)).card

/-- Sojourn time for customer `i`: number of slots spent in the system. -/
def W (inSys : Fin N → Fin T → Bool) (i : Fin N) : Nat :=
  (Finset.univ.filter (fun t : Fin T => inSys i t = true)).card

/--
Discrete-time double counting:

`∑_t L(t) = ∑_i W(i)`.

This is the core combinatorial identity underlying Little's law
(after dividing by total time and taking limits/expectations).
-/
theorem sum_L_eq_sum_W (inSys : Fin N → Fin T → Bool) :
    (∑ t : Fin T, L (N:=N) (T:=T) inSys t) = (∑ i : Fin N, W (N:=N) (T:=T) inSys i) := by
  classical
  -- Rewrite both sides as double sums of indicator functions, then commute summation.
  --
  -- `Finset.card_filter` turns a filtered-cardinality into a sum of `if _ then 1 else 0`.
  -- `Finset.sum_comm` swaps the order of summation.
  --
  -- NOTE: This is intentionally written in a deterministic, non-LLM-dependent style.
  simpa [L, W, Fintype.sum, Finset.card_filter] using
    (Finset.sum_comm (s := (Finset.univ : Finset (Fin T)))
      (t := (Finset.univ : Finset (Fin N)))
      (f := fun (t : Fin T) (i : Fin N) => (if inSys i t = true then (1 : Nat) else 0)))

end LeanAtlas.Toolbox.Queueing.LittleSlot
