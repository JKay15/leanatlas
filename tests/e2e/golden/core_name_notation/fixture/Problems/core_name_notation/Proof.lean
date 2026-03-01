import Problems.core_name_notation.Spec
import Mathlib.Algebra.BigOperators.Group.Finset.Basic
import Mathlib.Data.Finset.Basic

namespace Problems.core_name_notation

-- Intentionally missing: `open scoped BigOperators`

theorem main : (∑ i ∈ Finset.range 3, i) = expected := by
  decide

end Problems.core_name_notation
