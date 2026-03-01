/-
LeanAtlas toolbox entrypoint.

Default rule:
- Problem files should prefer `import LeanAtlas.Toolbox.Imports` first.
- Add more imports only when needed (record them in RetrievalTrace).
-/
import Mathlib

-- Promoted tools (test-fixture overlay)
import LeanAtlas.Toolbox.Analysis.LogBarrier
import LeanAtlas.Toolbox.Queueing.Lindley
