import Problems.core_type_mismatch.Spec
import Mathlib.Data.Int.Basic

namespace Problems.core_type_mismatch

theorem main : Nat := by
  -- Intentional type mismatch: Int is not Nat
  exact (0 : Int)

end Problems.core_type_mismatch
