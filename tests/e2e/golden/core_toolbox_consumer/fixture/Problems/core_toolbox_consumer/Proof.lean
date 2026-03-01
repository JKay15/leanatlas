import Problems.core_toolbox_consumer.Spec
import LeanAtlas.Toolbox.Imports

namespace Problems.core_toolbox_consumer

theorem main : True := by
  -- Prove by reusing a toolbox lemma (tests that LeanAtlas imports are wired).
  exact LeanAtlas.Toolbox.toolbox_true

end Problems.core_toolbox_consumer
