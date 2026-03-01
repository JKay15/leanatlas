/--
Source-file import edge extractor (LeanAtlas tooling).

Goal:
- Deterministically extract **direct** import edges for a list of `.lean` source files.
- Prefer Lean's own import parser via `import-graph` (no hand-rolled regex).

Usage (from repo root):
  lake env lean --run scripts/import_edges_from_source.lean -- <file1.lean> <file2.lean> ...

Output (stdout): JSON
  {
    "version": "0.1",
    "edges": [
      {"module": "Foo.Bar", "imports": ["A", "B"]},
      ...
    ],
    "errors": [
      {"path": "...", "message": "..."},
      ...
    ]
  }

Notes:
- This tool parses *source* files directly; it does not require a built environment.
- The Python GC tooling will canonicalize + filter the result.
-/

import ImportGraph.Imports.FromSource
import Lean.Data.Json

open Lean

namespace LeanAtlas.ImportEdgesFromSource

private def normalizePath (s : String) : String :=
  let s := s.replace "\\" "/"
  if s.startsWith "./" then s.drop 2 else s

private def moduleNameFromPathString (s0 : String) : Name :=
  let s := normalizePath s0
  let s := if s.endsWith ".lean" then s.dropRight 5 else s
  let parts := s.splitOn "/"
  parts.foldl (fun acc p => Name.str acc p) Name.anonymous

private def jsonStr (s : String) : Json :=
  Json.str s

private def jsonObj (kvs : List (String × Json)) : Json :=
  Json.mkObj kvs

private def jsonArr (xs : List Json) : Json :=
  Json.arr xs.toArray

private def edgeObj (mod : String) (imports : List String) : Json :=
  jsonObj [
    ("module", jsonStr mod),
    ("imports", jsonArr (imports.map jsonStr))
  ]

private def errorObj (path msg : String) : Json :=
  jsonObj [
    ("path", jsonStr path),
    ("message", jsonStr msg)
  ]

private def run (paths : List String) : IO Unit := do
  let mut edges : List Json := []
  let mut errs  : List Json := []

  -- Make output stable across runs: sort input paths.
  let paths := paths.qsort (fun a b => a < b)

  for p in paths do
    let fp : System.FilePath := ⟨p⟩
    try
      let imps ← ImportGraph.Imports.FromSource.findImportsFromSource fp
      let modName := (moduleNameFromPathString p).toString
      let imports := (imps.toList.map (fun n => n.toString)).qsort (fun a b => a < b)
      edges := edgeObj modName imports :: edges
    catch e =>
      errs := errorObj p (toString e) :: errs

  -- Stable output: sort edges by module name (already derived from sorted paths).
  let out := jsonObj [
    ("version", jsonStr "0.1"),
    ("edges", jsonArr edges.reverse),
    ("errors", jsonArr errs.reverse)
  ]
  IO.println out.pretty

end LeanAtlas.ImportEdgesFromSource

/-- Entry point. -/
#eval do
  let args ← IO.getArgs
  -- Allow users to pass `--` before paths; Lean includes it in args sometimes.
  let paths := args.filter (fun a => a != "--")
  LeanAtlas.ImportEdgesFromSource.run paths
