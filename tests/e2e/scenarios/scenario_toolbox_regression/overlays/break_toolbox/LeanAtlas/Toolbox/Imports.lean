/--
This file is intentionally broken for the nightly regression scenario.
It must cause a compile error *outside* Problems/<slug>/... so the judge emits ERROR_OUTSIDE_SCOPE.
-/

import Mathlib

namespace LeanAtlas.Toolbox

-- Broken on purpose: missing `:=` proof.
theorem broken_outside_problem : False := by
  -- no proof

end LeanAtlas.Toolbox
