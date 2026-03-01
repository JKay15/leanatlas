import Lake
open Lake DSL

/-
E2E fixture project.

Pinned to a *stable* Lean + mathlib tag to keep the executable tests reproducible.
-/

package leanatlas_e2e where

require mathlib from git
  "https://github.com/leanprover-community/mathlib4" @ "v4.28.0"

lean_lib Problems where
  -- Keep default srcDir to map modules like `Problems.foo.Bar`
  -- to paths `Problems/foo/Bar.lean`.


lean_lib LeanAtlas where
  -- Keep default srcDir to map modules like `LeanAtlas.Toolbox.Basics`
  -- to paths `LeanAtlas/Toolbox/Basics.lean`.
