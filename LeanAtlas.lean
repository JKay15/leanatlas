/-
LeanAtlas root module.

This repository is intentionally minimal: most “meat” lives in Problems/ and agent workflow tooling.
We keep a tiny Lean library so that `lake build` can succeed and downstream tools (LSP, caching)
have a stable entrypoint.
-/

import LeanAtlas.Toolbox.Imports
