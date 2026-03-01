import Lake
open Lake DSL

package leanatlas where
  -- `lake test` and `lake lint` are wired to our workflow test system.
  testDriver := "lake_test_driver"
  lintDriver := "lake_lint_driver"

require mathlib from git
  "https://github.com/leanprover-community/mathlib4" @ "v4.28.0"

-- import-graph: module import graph analysis (used by GCGate + visualization)
require importGraph from git
  "https://github.com/leanprover-community/import-graph" @ "v4.28.0"

@[default_target]
lean_lib LeanAtlas where
  -- Lean files live under `LeanAtlas/**`
  roots := #[`LeanAtlas]

lean_lib Problems where
  -- Problem modules live under `Problems/**`
  roots := #[`Problems]

/-- Run repository test workflow via the shell test driver. -/
script lake_test_driver (args) do
  let child ← IO.Process.spawn {
    cmd := "bash"
    args := #["scripts/lake_test_driver.sh"] ++ args.toArray
    stdin := .inherit
    stdout := .inherit
    stderr := .inherit
  }
  child.wait

/-- Run repository lint workflow via the shell lint driver. -/
script lake_lint_driver (args) do
  let child ← IO.Process.spawn {
    cmd := "bash"
    args := #["scripts/lake_lint_driver.sh"] ++ args.toArray
    stdin := .inherit
    stdout := .inherit
    stderr := .inherit
  }
  child.wait
