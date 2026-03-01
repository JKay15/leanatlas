#!/usr/bin/env python3
"""LeanAtlas Incubator GC (V0: deterministic state machine + reachability MVP).

This tool closes the *GC loop* for Incubator Seeds **without deleting code**.

What it controls:
- `tools/index/gc_state.json`: per-seed lifecycle state
    - active / quarantined / archived
- Search visibility / retrieval priority (downstream tools read this state).

What it does NOT do in V0:
- Move files across directories
- Delete `.lean` files

Why conservative?
- GC mistakes are catastrophic (you "lose" tools).
- V0 aims to make the workflow auditable + deterministic first.

Truth sources:
- Lean environment is the only correctness authority.
- GC is a library-maintenance policy tool (visibility/priority), not semantics.

CLI:
  python tools/gc/gc.py propose --repo-root <path> --out-root <dir>
  python tools/gc/gc.py apply   --repo-root <path> --plan <GCPlan.json> --out-root <dir> --mode MAINTAINER [--dry-run]

Outputs:
- propose: <out-root>/GCPlan.json, GCReport.json, GCReport.md
- apply:   <out-root>/GCReport.json, GCReport.md (+ updates gc_state.json unless --dry-run)

See contracts:
- docs/contracts/GC_GATE_CONTRACT.md
- docs/contracts/GC_STATE_CONTRACT.md
- docs/contracts/PROBLEM_STATE_CONTRACT.md
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow `from tools.*` imports when executing as a script (sys.path[0] == tools/...).
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import argparse
import json
import os
import re
import shutil

from tools.workflow.run_cmd import run_cmd
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple


# -------------------------
# Canonical I/O utilities
# -------------------------

def _canonical_dump(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _write_text(p: Path, s: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(s, encoding="utf-8")


def _write_json(p: Path, obj: Any) -> None:
    _write_text(p, _canonical_dump(obj))


def _load_json(p: Path) -> Any:
    return json.loads(p.read_text(encoding="utf-8"))


# -------------------------
# Paths / IDs
# -------------------------

def _gc_state_path(repo_root: Path) -> Path:
    return repo_root / "tools" / "index" / "gc_state.json"


def _roots_json_path(repo_root: Path) -> Path:
    return repo_root / "tools" / "gc" / "roots.json"


def _local_gcroots_dir(repo_root: Path) -> Path:
    return repo_root / "tools" / "gc" / "gcroots"


def _module_to_relpath(module_name: str) -> Path:
    return Path(*module_name.split(".")).with_suffix(".lean")


def _relpath_to_module(relpath: Path) -> str:
    # Lean module names are path segments joined by '.' (repo root is srcDir)
    rp = relpath.as_posix()
    if rp.startswith("./"):
        rp = rp[2:]
    if rp.endswith(".lean"):
        rp = rp[:-5]
    return rp.replace("/", ".")


def _seed_domain_id(seed_id: str) -> str:
    """Infer domain bucket from the canonical path layout.

    Expected seed module prefix:
      LeanAtlas.Incubator.Seeds.<domain_id>....

    If shape deviates, return 'UNKNOWN'.
    """
    parts = seed_id.split(".")
    try:
        i = parts.index("Seeds")
        return parts[i + 1] if i + 1 < len(parts) else "UNKNOWN"
    except ValueError:
        return "UNKNOWN"


def _is_seed_module(m: str) -> bool:
    return m.startswith("LeanAtlas.Incubator.Seeds.")


def _is_toolbox_module(m: str) -> bool:
    return m.startswith("LeanAtlas.Toolbox.")


# -------------------------
# GC state
# -------------------------

def _ensure_gc_state(repo_root: Path) -> Dict[str, Any]:
    p = _gc_state_path(repo_root)
    if p.exists():
        obj = _load_json(p)
        if not isinstance(obj, dict):
            raise ValueError("gc_state.json must be an object")
        obj.setdefault("version", "0.2")
        obj.setdefault("seeds", {})
        if not isinstance(obj["seeds"], dict):
            raise ValueError("gc_state.json: seeds must be an object")
        return obj
    return {"version": "0.2", "seeds": {}}


def _apply_action(
    *,
    state: Dict[str, Any],
    seed_id: str,
    action: str,
    evidence: Dict[str, Any],
    meta_update: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, str]:
    """Apply one GCPlan action to gc_state.

    Returns (changed, new_state).

    V0 rule: only mutate `tools/index/gc_state.json`.
    """
    seeds = state.setdefault("seeds", {})
    rec = seeds.get(seed_id)
    if not isinstance(rec, dict):
        rec = {"state": "active"}

    old = str(rec.get("state", "active"))

    new = old
    a = action.lower().strip()
    if a in ("quarantine", "quarantined"):
        new = "quarantined"
    elif a in ("archive", "archived"):
        new = "archived"
    elif a in ("activate", "active", "revive", "restore"):
        new = "active"
    elif a in ("noop", "keep", "meta"):
        new = old
    else:
        # Unknown action => no-op; still record evidence.
        new = old

    rec["state"] = new

    # Merge meta update (open-world, but deterministic).
    if isinstance(meta_update, dict):
        for k, v in meta_update.items():
            rec[k] = v

    # Merge evidence into reason (audit trail).
    rec.setdefault("reason", {})
    if isinstance(rec.get("reason"), dict) and isinstance(evidence, dict):
        rec["reason"].update({"last_action": action, **evidence})

    # Deterministic path hint (optional but helpful; contract test enforces if present).
    if "path_hint" not in rec:
        rec["path_hint"] = str(_module_to_relpath(seed_id).as_posix())

    seeds[seed_id] = rec
    return (new != old) or bool(meta_update), new


# -------------------------
# ProblemState / domain clock
# -------------------------

def _load_problem_states(repo_root: Path) -> Dict[str, Dict[str, Any]]:
    problems_dir = repo_root / "Problems"
    out: Dict[str, Dict[str, Any]] = {}
    if not problems_dir.exists():
        return out

    for p in sorted(problems_dir.iterdir()):
        if not p.is_dir():
            continue
        slug = p.name
        if slug == "_template":
            continue
        state_path = p / "State.json"
        if not state_path.exists():
            continue
        try:
            st = _load_json(state_path)
            if isinstance(st, dict):
                out[slug] = st
        except Exception:
            continue
    return out


def _domain_progress_clock(problem_states: Dict[str, Dict[str, Any]]) -> Dict[str, int]:
    """Domain progress clock = count of problems in that domain that ever_succeeded."""
    counts: Dict[str, int] = {}
    for _slug, st in problem_states.items():
        if not isinstance(st, dict):
            continue
        dom = ((st.get("domain") or {}) if isinstance(st.get("domain"), dict) else {})
        domain_id = str(dom.get("domain_id", "UNKNOWN"))
        if bool(st.get("ever_succeeded", False)):
            counts[domain_id] = counts.get(domain_id, 0) + 1
    return counts


def _recency_key(st: Dict[str, Any]) -> Tuple[int, str, int, str]:
    """Deterministic recency proxy.

    We avoid filesystem mtimes. We use:
    - has_last_run (1/0)
    - last_run.run_id (string, expected sortable)
    - counters.attempts (int)
    - slug (string)
    """
    lr = st.get("last_run") if isinstance(st.get("last_run"), dict) else {}
    run_id = str((lr or {}).get("run_id", ""))
    has_lr = 1 if run_id else 0
    ctr = st.get("counters") if isinstance(st.get("counters"), dict) else {}
    attempts = int((ctr or {}).get("attempts", 0))
    slug = str(st.get("problem_slug", ""))
    return (has_lr, run_id, attempts, slug)


def _select_active_roots_per_domain(
    problem_states: Dict[str, Dict[str, Any]],
    *,
    k_active: int,
    k_success: int,
    k_triaged: int,
    unknown_bucket: str,
) -> Dict[str, Dict[str, List[str]]]:
    """Return per-domain selected problem slugs.

    Output shape:
      {domain_id: {"ACTIVE": [...], "SUCCESS": [...], "TRIAGED": [...]}}
    """
    buckets: Dict[str, Dict[str, List[Tuple[Tuple[int, str, int, str], str]]]] = {}

    for slug, st in problem_states.items():
        dom = st.get("domain") if isinstance(st.get("domain"), dict) else {}
        domain_id = str((dom or {}).get("domain_id", unknown_bucket) or unknown_bucket)
        status = str(st.get("status", "NEW"))
        if status not in ("ACTIVE", "SUCCESS", "TRIAGED"):
            continue
        buckets.setdefault(domain_id, {}).setdefault(status, [])
        buckets[domain_id][status].append((_recency_key(st), slug))

    out: Dict[str, Dict[str, List[str]]] = {}
    for domain_id, per_status in buckets.items():
        out[domain_id] = {"ACTIVE": [], "SUCCESS": [], "TRIAGED": []}
        for status, items in per_status.items():
            # Sort descending by recency key
            items_sorted = sorted(items, key=lambda x: x[0], reverse=True)
            k = {"ACTIVE": k_active, "SUCCESS": k_success, "TRIAGED": k_triaged}[status]
            out[domain_id][status] = [slug for _k, slug in items_sorted[:k]]
    return out


# -------------------------
# Import graph (reachability)
# -------------------------

IMPORT_RE = re.compile(r"^\s*import\s+(?P<rest>.+?)\s*$")


def _have_cmd(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def _scan_imports_fallback_text(path: Path) -> List[str]:
    """Very conservative fallback: scan `import` lines (no macro parsing).

    This exists only as a fallback when import-graph is unavailable.
    """
    if not path.exists():
        return []
    out: List[str] = []
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            # Remove single-line comments.
            line = raw.split("--", 1)[0].strip()
            if not line:
                continue
            m = IMPORT_RE.match(line)
            if not m:
                continue
            rest = m.group("rest")
            # Split on whitespace; Lean import syntax uses spaces.
            toks = [t.strip() for t in rest.split() if t.strip()]
            out.extend(toks)
    except Exception:
        return []
    # unique + stable
    return sorted(set(out))


def _chunked(xs: List[Path], n: int) -> Iterable[List[Path]]:
    for i in range(0, len(xs), n):
        yield xs[i : i + n]


def _import_edges_via_importgraph_from_source(repo_root: Path, relpaths: List[Path]) -> Tuple[Dict[str, List[str]], Dict[str, Any]]:
    """Use scripts/import_edges_from_source.lean (import-graph FromSource parser).

    Returns:
      edges: {module: [import1, import2, ...]}
      meta: provider metadata (errors, etc.)
    """
    script = repo_root / "scripts" / "import_edges_from_source.lean"
    if not script.exists():
        raise RuntimeError("missing scripts/import_edges_from_source.lean")
    if not _have_cmd("lake"):
        raise RuntimeError("lake not found")

    edges: Dict[str, List[str]] = {}
    errors: List[Dict[str, Any]] = []

    log_dir = repo_root / ".cache" / "leanatlas" / "cmd_logs" / "gc"

    # Chunk to avoid command-line length limits.
    for ci, chunk in enumerate(_chunked(relpaths, 200)):
        cmd = [
            "lake",
            "env",
            "lean",
            "--run",
            str(script.relative_to(repo_root)),
            "--",
            *[p.as_posix() for p in chunk],
        ]
        res = run_cmd(
            cmd=cmd,
            cwd=repo_root,
            log_dir=log_dir,
            label=f"gc_importgraph_{ci:03d}",
            capture_text=True,
        )
        if int(res.span.get("exit_code", 1)) != 0:
            raise RuntimeError(
                "import-graph FromSource runner failed (non-zero rc)\n"
                f"cmd: {' '.join(cmd)}\n"
                f"stdout:\n{res.stdout_text or ''}\n"
                f"stderr:\n{res.stderr_text or ''}\n"
            )
        try:
            data = json.loads(res.stdout_text or "")
        except Exception as e:
            raise RuntimeError(
                "import-graph FromSource runner returned non-JSON stdout\n"
                f"error: {e}\n"
                f"stdout:\n{res.stdout_text or ''}\n"
                f"stderr:\n{res.stderr_text or ''}\n"
            )

        for e in (data.get("edges") or []):
            if not isinstance(e, dict):
                continue
            m = str(e.get("module", ""))
            imps = e.get("imports")
            if not m or not isinstance(imps, list):
                continue
            edges[m] = sorted(set(str(x) for x in imps if isinstance(x, str)))

        for er in (data.get("errors") or []):
            if isinstance(er, dict):
                errors.append(er)

    meta = {
        "provider": "import_graph_from_source",
        "script": str(script.relative_to(repo_root)),
        "errors": errors,
    }
    return edges, meta


def _collect_local_modules(repo_root: Path) -> Dict[str, Path]:
    """Collect local `.lean` modules (LeanAtlas + Problems) and map module->relpath."""
    modules: Dict[str, Path] = {}

    def add_tree(root_rel: str) -> None:
        root = repo_root / root_rel
        if not root.exists():
            return
        for p in root.rglob("*.lean"):
            # Ignore build/hidden trees
            if any(seg.startswith(".") for seg in p.relative_to(repo_root).parts):
                continue
            rel = p.relative_to(repo_root)
            mod = _relpath_to_module(rel)
            modules[mod] = rel

    add_tree("LeanAtlas")
    add_tree("Problems")
    return modules


def _build_local_import_graph(
    *,
    repo_root: Path,
    modules: Dict[str, Path],
) -> Tuple[Dict[str, List[str]], Dict[str, Any]]:
    """Return adjacency list among local modules only."""
    relpaths = sorted(modules.values(), key=lambda p: p.as_posix())

    provider_meta: Dict[str, Any] = {}
    edges_raw: Dict[str, List[str]] = {}

    # Prefer import-graph (FromSource). Fallback to text scan.
    try:
        edges_raw, provider_meta = _import_edges_via_importgraph_from_source(repo_root, relpaths)
    except Exception as e:
        provider_meta = {
            "provider": "fallback_text_scan",
            "error": str(e),
        }
        for mod, rel in modules.items():
            abs_p = repo_root / rel
            edges_raw[mod] = _scan_imports_fallback_text(abs_p)

    # Filter edges to local modules only.
    local_set: Set[str] = set(modules.keys())
    adj: Dict[str, List[str]] = {}
    for mod, imps in edges_raw.items():
        if mod not in local_set:
            continue
        imps_local = [i for i in imps if i in local_set]
        adj[mod] = sorted(set(imps_local))

    provider_meta["local_modules"] = len(modules)
    provider_meta["local_edges"] = sum(len(v) for v in adj.values())
    return adj, provider_meta


def _bfs(start: Iterable[str], adj: Dict[str, List[str]]) -> Set[str]:
    start_set = [s for s in start if s]
    seen: Set[str] = set(start_set)
    stack: List[str] = list(start_set)
    while stack:
        cur = stack.pop()
        for nxt in adj.get(cur, []):
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return seen


# -------------------------
# Roots
# -------------------------

def _read_pinned_roots(repo_root: Path) -> Tuple[List[str], Dict[str, Any]]:
    p = _roots_json_path(repo_root)
    if not p.exists():
        return [], {"source": "roots.json", "missing": True}
    try:
        obj = _load_json(p)
        pinned = obj.get("pinned_seeds") or []
        if not isinstance(pinned, list):
            pinned = []
        pinned_s = [str(x) for x in pinned if isinstance(x, str)]
        return sorted(set(pinned_s)), {"source": "roots.json", "missing": False, "version": obj.get("version")}
    except Exception as e:
        return [], {"source": "roots.json", "missing": False, "error": str(e)}


def _read_symlink_roots(repo_root: Path) -> Tuple[List[str], Dict[str, Any]]:
    d = _local_gcroots_dir(repo_root)
    if not d.exists():
        return [], {"source": "gcroots", "missing": True}
    pinned: List[str] = []
    errors: List[str] = []

    try:
        for p in sorted(d.iterdir()):
            try:
                if not p.is_symlink():
                    continue
                target = p.resolve()
                # Convert target to repo-relative path if possible.
                try:
                    rel = target.relative_to(repo_root)
                except Exception:
                    errors.append(f"symlink target not under repo_root: {p} -> {target}")
                    continue
                if rel.suffix != ".lean":
                    continue
                pinned.append(_relpath_to_module(rel))
            except Exception as e:
                errors.append(f"{p}: {e}")
    except Exception as e:
        return [], {"source": "gcroots", "missing": False, "error": str(e)}

    return sorted(set(pinned)), {"source": "gcroots", "missing": False, "errors": errors}


# -------------------------
# Policy (V0 defaults)
# -------------------------

def _default_policy() -> Dict[str, Any]:
    return {
        "mark_strategy": "reachability",
        "age_clock": "domain_progress_problems",
        "reachability_sources": ["imports"],
        "two_phase_delete_enforced": True,
        "active_problem_roots": {
            "strategy": "per_domain_layered",
            "k_active_per_domain": 1,
            "k_success_per_domain": 2,
            "k_triaged_per_domain": 1,
            "unknown_domain_bucket": "UNKNOWN",
            "problem_entrypoints": ["Spec", "Proof", "Cache"],
        },
        "thresholds": {
            "grace_new_seed": 2,
            "quarantine": 8,
            "archive": 24,
            "revival_grace": 4,
            "revival_pending_window": 6,
        },
    }


# -------------------------
# Plan/report
# -------------------------

def _make_report_md(report: Dict[str, Any]) -> str:
    pol = report.get("policy", {}) if isinstance(report.get("policy"), dict) else {}
    summ = report.get("summary", {}) if isinstance(report.get("summary"), dict) else {}
    meta = report.get("meta", {}) if isinstance(report.get("meta"), dict) else {}

    lines: List[str] = []
    lines.append(f"# GCReport ({meta.get('phase','')})")
    lines.append("")
    lines.append("## Summary")
    for k in [
        "seeds_total",
        "seeds_reachable",
        "seeds_unreachable",
        "actions_total",
        "actions_quarantine",
        "actions_archive",
        "actions_activate",
    ]:
        if k in summ:
            lines.append(f"- {k}: {summ.get(k)}")
    lines.append("")
    lines.append("## Policy")
    lines.append("```json")
    lines.append(_canonical_dump(pol).rstrip())
    lines.append("```")
    lines.append("")
    lines.append("## Notes")
    lines.append("- V0 never deletes code; it only updates gc_state.json.")
    lines.append("- Reachability is computed from local source import edges (prefer import-graph; fallback to text scan).")
    return "\n".join(lines) + "\n"


def _make_plan(
    *,
    repo_root: Path,
    policy: Dict[str, Any],
    actions: List[Dict[str, Any]],
    provider_meta: Dict[str, Any],
    roots_meta: Dict[str, Any],
    domain_clock: Dict[str, int],
) -> Dict[str, Any]:
    return {
        "version": "0.1",
        "meta": {
            "phase": "propose",
            "repo_root": str(repo_root),
            "import_graph": provider_meta,
            "roots": roots_meta,
            "domain_clock": domain_clock,
        },
        "policy": policy,
        "actions": actions,
    }


def _make_report(
    *,
    repo_root: Path,
    phase: str,
    policy: Dict[str, Any],
    actions: List[Dict[str, Any]],
    provider_meta: Dict[str, Any],
    roots_meta: Dict[str, Any],
    summary: Dict[str, Any],
    extra_meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    meta = {
        "phase": phase,
        "repo_root": str(repo_root),
        "import_graph": provider_meta,
        "roots": roots_meta,
    }
    if isinstance(extra_meta, dict):
        meta.update(extra_meta)

    return {
        "version": "0.1",
        "meta": meta,
        "policy": policy,
        "actions": actions,
        "safety": {
            "two_phase_delete_enforced": True,
            "notes": "V0 never deletes code; only updates tools/index/gc_state.json",
        },
        "summary": summary,
    }


# -------------------------
# propose
# -------------------------

def cmd_propose(repo_root: Path, out_root: Path, mode: str) -> int:
    # Mode doesn't restrict propose, but we record it for audit.
    mode = mode.upper().strip()

    policy = _default_policy()
    thr = policy["thresholds"]
    roots_pol = policy["active_problem_roots"]

    # Load truth sources
    gc_state = _ensure_gc_state(repo_root)
    problem_states = _load_problem_states(repo_root)
    domain_clock = _domain_progress_clock(problem_states)

    selected = _select_active_roots_per_domain(
        problem_states,
        k_active=int(roots_pol["k_active_per_domain"]),
        k_success=int(roots_pol["k_success_per_domain"]),
        k_triaged=int(roots_pol["k_triaged_per_domain"]),
        unknown_bucket=str(roots_pol.get("unknown_domain_bucket", "UNKNOWN")),
    )

    # Local modules + local import graph
    modules = _collect_local_modules(repo_root)
    adj, provider_meta = _build_local_import_graph(repo_root=repo_root, modules=modules)

    seed_modules = sorted([m for m in modules.keys() if _is_seed_module(m)])
    toolbox_modules = sorted([m for m in modules.keys() if _is_toolbox_module(m)])

    pinned_json, pinned_json_meta = _read_pinned_roots(repo_root)
    pinned_syms, pinned_syms_meta = _read_symlink_roots(repo_root)
    pinned_all = sorted(set(pinned_json) | set(pinned_syms))

    # Root problem entrypoints
    entrypoints: List[str] = [str(x) for x in roots_pol.get("problem_entrypoints", ["Spec", "Proof", "Cache"]) if isinstance(x, str)]

    selected_problem_slugs: List[str] = []
    for dom, per in selected.items():
        for st in ("ACTIVE", "SUCCESS", "TRIAGED"):
            selected_problem_slugs.extend(per.get(st, []) or [])
    selected_problem_slugs = sorted(set(selected_problem_slugs))

    problem_root_modules: Dict[str, List[str]] = {}
    for slug in selected_problem_slugs:
        mods: List[str] = []
        for ep in entrypoints:
            m = f"Problems.{slug}.{ep}"
            if m in modules:
                mods.append(m)
        problem_root_modules[slug] = mods

    all_problem_root_modules: List[str] = sorted({m for ms in problem_root_modules.values() for m in ms})

    roots_meta = {
        "mode": mode,
        "pinned": {
            "roots_json": pinned_json_meta,
            "gcroots": pinned_syms_meta,
            "count": len(pinned_all),
            "seed_ids": pinned_all,
        },
        "toolbox_root_modules": {
            "count": len(toolbox_modules),
            "modules": toolbox_modules[:50],
            "truncated": len(toolbox_modules) > 50,
        },
        "active_problem_roots": {
            "policy": {
                "k_active_per_domain": roots_pol["k_active_per_domain"],
                "k_success_per_domain": roots_pol["k_success_per_domain"],
                "k_triaged_per_domain": roots_pol["k_triaged_per_domain"],
            },
            "selected": selected,
            "entrypoints": entrypoints,
            "problem_root_modules": {k: v for k, v in problem_root_modules.items()},
        },
    }

    # Reachability sets
    reach_pinned = _bfs(pinned_all, adj)
    reach_toolbox = _bfs(toolbox_modules, adj)

    reach_by_problem: Dict[str, Set[str]] = {}
    for slug, roots in problem_root_modules.items():
        if not roots:
            reach_by_problem[slug] = set()
            continue
        reach_by_problem[slug] = _bfs(roots, adj)

    # Aggregate reachable seeds and provenance
    reachable_from_pinned: Set[str] = set(m for m in reach_pinned if _is_seed_module(m))
    reachable_from_toolbox: Set[str] = set(m for m in reach_toolbox if _is_seed_module(m))
    reachable_from_problems: Dict[str, List[str]] = {s: [] for s in seed_modules}

    for slug, vis in reach_by_problem.items():
        for m in vis:
            if _is_seed_module(m):
                reachable_from_problems.setdefault(m, []).append(slug)

    # Union
    reachable_any: Set[str] = set(reachable_from_pinned) | set(reachable_from_toolbox)
    for seed_id, slugs in reachable_from_problems.items():
        if slugs:
            reachable_any.add(seed_id)

    # Decide actions
    actions: List[Dict[str, Any]] = []

    seeds_state = gc_state.get("seeds", {}) if isinstance(gc_state.get("seeds"), dict) else {}

    def get_rec(seed_id: str) -> Dict[str, Any]:
        rec = seeds_state.get(seed_id)
        return rec if isinstance(rec, dict) else {}

    def clock_for(seed_id: str) -> int:
        return int(domain_clock.get(_seed_domain_id(seed_id), 0))

    def ensure_int(x: Any, default: int) -> int:
        try:
            return int(x)
        except Exception:
            return default

    for seed_id in seed_modules:
        rec = get_rec(seed_id)
        state = str(rec.get("state", "active"))

        dom = _seed_domain_id(seed_id)
        clk = clock_for(seed_id)

        introduced_at = ensure_int(rec.get("introduced_at_clock"), clk)
        last_used = ensure_int(rec.get("last_used_clock"), introduced_at)

        # If clock decreased (domain reclassification / removed states), clamp.
        if last_used > clk:
            last_used = clk
        if introduced_at > clk:
            introduced_at = clk

        staleness = max(0, clk - last_used)
        age = max(0, clk - introduced_at)

        pinned = seed_id in pinned_all
        reachable = seed_id in reachable_any
        reached_by = []
        if pinned:
            reached_by.append("pinned")
        if seed_id in reachable_from_toolbox:
            reached_by.append("toolbox")
        if reachable_from_problems.get(seed_id):
            reached_by.append("active_problems")

        # "Use" signal (V0): reachability via active problems counts as a use.
        use_hits = sorted(set(reachable_from_problems.get(seed_id, []) or []))
        used = pinned or bool(use_hits) or (seed_id in reachable_from_toolbox)

        meta_update: Dict[str, Any] = {}
        # Initialize introduced_at deterministically when missing.
        if "introduced_at_clock" not in rec:
            meta_update["introduced_at_clock"] = introduced_at

        # Update last_used when used.
        if used:
            new_last_used = max(last_used, clk)
            if new_last_used != last_used or ("last_used_clock" not in rec):
                meta_update["last_used_clock"] = new_last_used
            if use_hits:
                meta_update["last_used_by_problems"] = use_hits[:20]

        # Revival grace window
        revival_grace_until = ensure_int(rec.get("revival_grace_until_clock"), -1)
        in_revival_grace = (revival_grace_until >= 0) and (clk <= revival_grace_until)

        # --- State machine decisions ---
        act: Optional[str] = None
        evidence: Dict[str, Any] = {
            "seed_id": seed_id,
            "domain_id": dom,
            "domain_clock": clk,
            "introduced_at_clock": introduced_at,
            "last_used_clock": last_used,
            "staleness": staleness,
            "age": age,
            "reachable": reachable,
            "reached_by": reached_by,
            "use_hits": use_hits,
            "current_state": state,
        }

        # Pinned implies active (strong safety).
        if pinned and state != "active":
            act = "activate"
            evidence["reason"] = "PINNED_ROOT_ENFORCES_ACTIVE"
            meta_update["revival_grace_until_clock"] = clk + int(thr["revival_grace"])
            meta_update["last_revival_clock"] = clk
            # Clear any pending fields if present.
            meta_update.pop("revival_pending", None)
            meta_update.pop("revival_pending_until_clock", None)

        # If used and quarantined -> revive.
        if act is None and used and state == "quarantined":
            act = "activate"
            evidence["reason"] = "USED_REVIVES_QUARANTINED"
            meta_update["revival_grace_until_clock"] = clk + int(thr["revival_grace"])
            meta_update["last_revival_clock"] = clk

        # Archived revival is two-stage unless pinned.
        if act is None and used and state == "archived":
            # If pinned, we would have hit the pinned branch above.
            pending = bool(rec.get("revival_pending", False))
            pending_until = ensure_int(rec.get("revival_pending_until_clock"), -1)
            pending_hits = rec.get("revival_pending_hits")
            if not isinstance(pending_hits, list):
                pending_hits = []
            pending_hits_s = [str(x) for x in pending_hits if isinstance(x, str)]

            within_window = pending and (pending_until >= 0) and (clk <= pending_until)
            new_hits = list(pending_hits_s)
            for h in use_hits:
                if h not in new_hits:
                    new_hits.append(h)

            if (not within_window) or (not pending):
                act = "quarantine"  # stage 1: restore to quarantined
                evidence["reason"] = "ARCHIVED_REVIVAL_STAGE1"
                meta_update["revival_pending"] = True
                meta_update["revival_pending_until_clock"] = clk + int(thr["revival_pending_window"])
                meta_update["revival_pending_hits"] = use_hits[:20]
            else:
                # Stage 2: need >=2 independent hits in window
                meta_update["revival_pending_hits"] = new_hits[:20]
                if len(new_hits) >= 2:
                    act = "activate"
                    evidence["reason"] = "ARCHIVED_REVIVAL_STAGE2"
                    meta_update["revival_pending"] = False
                    meta_update["revival_pending_until_clock"] = None
                    meta_update["revival_grace_until_clock"] = clk + int(thr["revival_grace"])
                    meta_update["last_revival_clock"] = clk

        # Collection actions only when NOT used.
        if act is None and (not used):
            # New seed grace (generational): protect newborn seeds for N domain ticks.
            if age < int(thr["grace_new_seed"]):
                evidence["reason"] = "NEW_SEED_GRACE"
            elif in_revival_grace:
                evidence["reason"] = "REVIVAL_GRACE"
            else:
                if state == "active" and staleness >= int(thr["quarantine"]):
                    act = "quarantine"
                    evidence["reason"] = "STALE_UNREACHABLE_QUARANTINE"
                elif state == "quarantined" and staleness >= int(thr["archive"]):
                    act = "archive"
                    evidence["reason"] = "STALE_UNREACHABLE_ARCHIVE"

        # If we have no state transition but have meta updates, emit a noop action.
        if act is None and meta_update:
            act = "meta"
            evidence["reason"] = evidence.get("reason", "META_UPDATE_ONLY")

        if act is not None:
            actions.append(
                {
                    "seed_id": seed_id,
                    "action": act,
                    "evidence": evidence,
                    "meta_update": meta_update,
                }
            )

    # Deterministic ordering
    actions = sorted(actions, key=lambda a: (str(a.get("seed_id")), str(a.get("action"))))

    # Summary
    seeds_total = len(seed_modules)
    seeds_reachable = len(reachable_any)
    seeds_unreachable = seeds_total - seeds_reachable

    def count_actions(name: str) -> int:
        return sum(1 for a in actions if str(a.get("action")) == name)

    summary = {
        "seeds_total": seeds_total,
        "seeds_reachable": seeds_reachable,
        "seeds_unreachable": seeds_unreachable,
        "actions_total": len(actions),
        "actions_quarantine": count_actions("quarantine"),
        "actions_archive": count_actions("archive"),
        "actions_activate": count_actions("activate"),
        "actions_meta": count_actions("meta"),
        "provider": provider_meta.get("provider"),
    }

    plan = _make_plan(
        repo_root=repo_root,
        policy=policy,
        actions=actions,
        provider_meta=provider_meta,
        roots_meta=roots_meta,
        domain_clock=domain_clock,
    )

    report = _make_report(
        repo_root=repo_root,
        phase="propose",
        policy=policy,
        actions=actions,
        provider_meta=provider_meta,
        roots_meta=roots_meta,
        summary=summary,
        extra_meta={"mode": mode},
    )

    out_root.mkdir(parents=True, exist_ok=True)
    _write_json(out_root / "GCPlan.json", plan)
    _write_json(out_root / "GCReport.json", report)
    _write_text(out_root / "GCReport.md", _make_report_md(report))
    print(f"[gc][propose] wrote {out_root/'GCPlan.json'}")
    return 0


# -------------------------
# apply
# -------------------------

def cmd_apply(repo_root: Path, plan_path: Path, out_root: Path, dry_run: bool, mode: str) -> int:
    mode = mode.upper().strip()
    if mode != "MAINTAINER":
        raise SystemExit("gc.apply requires --mode MAINTAINER (safety gate)")

    plan = _load_json(plan_path)
    if not isinstance(plan, dict):
        raise ValueError("GCPlan must be an object")

    actions_in = plan.get("actions") or []
    if not isinstance(actions_in, list):
        raise ValueError("GCPlan.actions must be an array")

    policy = plan.get("policy") if isinstance(plan.get("policy"), dict) else _default_policy()

    state = _ensure_gc_state(repo_root)

    applied_actions: List[Dict[str, Any]] = []
    changed_any = False

    for a in actions_in:
        if not isinstance(a, dict):
            continue
        seed = str(a.get("seed_id", a.get("seed", "")))
        action = str(a.get("action", ""))
        evidence = a.get("evidence") if isinstance(a.get("evidence"), dict) else {}
        meta_update = a.get("meta_update") if isinstance(a.get("meta_update"), dict) else None
        if not seed or not action:
            continue

        seed_file = repo_root / _module_to_relpath(seed)
        exists = seed_file.exists()

        changed, new_state = _apply_action(
            state=state,
            seed_id=seed,
            action=action,
            evidence={"seed_file_exists": bool(exists), **(evidence or {})},
            meta_update=meta_update,
        )
        changed_any = changed_any or changed

        applied_actions.append(
            {
                "seed_id": seed,
                "action": action,
                "evidence": {
                    "seed_file": str(seed_file),
                    "seed_file_exists": bool(exists),
                    "new_state": new_state,
                    **(evidence or {}),
                },
            }
        )

    # Write gc_state unless dry-run
    if changed_any and not dry_run:
        state_path = _gc_state_path(repo_root)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(_canonical_dump(state), encoding="utf-8")

    summary = {
        "actions_total": len(applied_actions),
        "state_changed": bool(changed_any),
    }

    report = _make_report(
        repo_root=repo_root,
        phase="apply",
        policy=policy,
        actions=applied_actions,
        provider_meta={"provider": "n/a"},
        roots_meta={"n/a": True},
        summary=summary,
        extra_meta={"dry_run": bool(dry_run), "mode": mode},
    )

    out_root.mkdir(parents=True, exist_ok=True)
    _write_json(out_root / "GCReport.json", report)
    _write_text(out_root / "GCReport.md", _make_report_md(report))
    print(f"[gc][apply] wrote {out_root/'GCReport.json'}")
    return 0


# -------------------------
# main
# -------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    ap_p = sub.add_parser("propose", help="Compute GCPlan + GCReport (reachability MVP, no deletion)")
    ap_p.add_argument("--repo-root", default=".")
    ap_p.add_argument("--out-root", required=True)
    ap_p.add_argument("--mode", default="OPERATOR", help="OPERATOR/MAINTAINER (recorded in report; propose is allowed in both)")

    ap_a = sub.add_parser("apply", help="Apply a GCPlan to gc_state.json (V0: state-only)")
    ap_a.add_argument("--repo-root", default=".")
    ap_a.add_argument("--plan", required=True)
    ap_a.add_argument("--out-root", required=True)
    ap_a.add_argument("--dry-run", action="store_true")
    ap_a.add_argument("--mode", required=True, help="Must be MAINTAINER")

    args = ap.parse_args()

    repo_root = Path(getattr(args, "repo_root", ".")).resolve()
    out_root = Path(getattr(args, "out_root", "./artifacts/gc")).resolve()

    if args.cmd == "propose":
        return cmd_propose(repo_root=repo_root, out_root=out_root, mode=str(args.mode))
    if args.cmd == "apply":
        plan_path = Path(args.plan).resolve()
        return cmd_apply(repo_root=repo_root, plan_path=plan_path, out_root=out_root, dry_run=bool(args.dry_run), mode=str(args.mode))

    raise SystemExit("unknown command")


if __name__ == "__main__":
    raise SystemExit(main())
