# Module visualization (Lean import graphs)

Lean projects scale faster when you can *see* the shape of the module DAG.

LeanAtlas supports module visualization via **import-graph** (a Lean/Lake tool) and a
**source-only** import edge extractor.

This doc focuses on **module-level** graphs (imports). It is not a theorem-level dependency graph.

## Option A: `lake exe graph` (import-graph)

**Best when your project builds.**

Prerequisite:
- Build at least the target modules you want to graph.

Typical usage:

- Create a PDF (may require Graphviz installed):

```bash
lake exe graph --to LeanAtlas artifacts/module_graph/LeanAtlas.pdf
```

- Create a stand-alone HTML graph:

```bash
lake exe graph --to LeanAtlas artifacts/module_graph/LeanAtlas.html
```

- Create a DOT file (Graphviz not required to generate the file):

```bash
lake exe graph --to LeanAtlas artifacts/module_graph/LeanAtlas.dot
```

Filtering:

```bash
lake exe graph --from Problems --to LeanAtlas artifacts/module_graph/Problems_to_LeanAtlas.dot
```

Notes:
- Output formats other than `.dot` typically require **Graphviz** (`dot`) available on your PATH.
- For large libraries, always prefer `--from/--to` filters. Whole-project graphs become unreadable.

## Option B: Source-only import edges (no built environment)

LeanAtlas ships a deterministic extractor:

- `scripts/import_edges_from_source.lean`

It parses direct `import ...` statements from source files and prints a stable JSON payload.

Example (repo root):

```bash
mkdir -p artifacts/module_graph
find LeanAtlas Problems -name '*.lean' -print0 \
  | xargs -0 lake env lean --run scripts/import_edges_from_source.lean -- \
  > artifacts/module_graph/import_edges.json
```

Then convert JSON edges to DOT using the repo tool:

```bash
./.venv/bin/python tools/module_graph/edges_to_dot.py \
  --in artifacts/module_graph/import_edges.json \
  --out artifacts/module_graph/import_edges.dot
```

(If you do not have `.venv`, replace with `uv run --locked python ...`.)

## Conventions

- Generated graphs belong under `artifacts/module_graph/**` (gitignored).
- Do not commit generated `.dot/.html/.pdf` unless explicitly requested for documentation.

## Prompt-driven usage (Codex App)

A copy/paste prompt template for generating these artifacts lives in:

- `docs/agents/CODEX_APP_PROMPTS.md` ("Module graph" section)
