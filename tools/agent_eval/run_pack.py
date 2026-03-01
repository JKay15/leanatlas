#!/usr/bin/env python3
"""Phase6 agent-eval runner (pack-level, v0).

This runner is deterministic-first:
- It validates a task pack + all referenced task.yaml files against JSON schemas.
- It emits a concrete `Plan.json`.
- Optionally, it materializes isolated workspaces (repo copy + fixture problem copy) per run.
- Optionally, it executes an external agent command via the global `run_cmd()` wrapper.

Output layout (pack-level):
  artifacts/agent_evals/<eval_id>/<stamp>/
    Plan.json
    runs/<task_id>/<variant_id>/
      PROMPT.md
      CONTEXT.json
      workspace/   # only for materialize/run

Notes:
- CI/core should use `--mode plan` for speed.
- Real executions should use `--mode materialize` or `--mode run`.
"""

from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path

_REPO_ROOT = _Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_REPO_ROOT))

import argparse
import datetime as _dt
import hashlib
import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import yaml
from jsonschema import Draft202012Validator

from tools.workflow.run_cmd import run_cmd
from tools.workflow.shared_cache import ensure_workspace_lake_packages
from tools.agent_eval.pins_used import ensure_pins_used


REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_TASK = REPO_ROOT / "docs" / "schemas" / "AgentEvalTask.schema.json"


@dataclass(frozen=True)
class TaskVariant:
    task_id: str
    problem_slug: str
    variant_id: str
    prompt: str
    gptpro_hint: str
    expected: Dict[str, Any]
    # Optional expectations for deterministic grading (kept out of the prompt).
    tool_delta: Dict[str, Any]
    skill_delta: Dict[str, Any]
    tags: List[str]
    # Optional maintainer-provided delta applied onto the fixture problem before the run.
    # This is NOT an agent patch and therefore does not violate OPERATOR patch scope.
    fixture_overlay_dir: Optional[str] = None


def _utc_stamp() -> str:
    return _dt.datetime.utcnow().replace(microsecond=0).isoformat().replace(":", "") + "Z"


def _sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return data


def _load_json_schema(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_json(instance: Any, schema: Dict[str, Any], what: str) -> None:
    v = Draft202012Validator(schema)
    errors = sorted(v.iter_errors(instance), key=lambda e: e.path)
    if errors:
        lines = [f"{what} failed schema validation ({len(errors)} errors):"]
        for e in errors[:20]:
            loc = "/".join([str(p) for p in e.path]) or "<root>"
            lines.append(f"- {loc}: {e.message}")
        if len(errors) > 20:
            lines.append(f"- ... {len(errors)-20} more")
        raise ValueError("\n".join(lines))


def _discover_task_refs(pack_yaml: Dict[str, Any]) -> List[Tuple[str, Optional[List[str]]]]:
    """Return [(task_id, variant_ids_or_None)]."""
    entries = pack_yaml.get("tasks")
    if not isinstance(entries, list) or not entries:
        raise ValueError("pack.yaml must contain a non-empty `tasks:` list")

    out: List[Tuple[str, Optional[List[str]]]] = []
    for e in entries:
        if isinstance(e, str):
            tid = e
            out.append((tid, None))
            continue
        if not isinstance(e, dict):
            raise ValueError("pack.yaml tasks entries must be strings or mappings")
        tid = e.get("task_id")
        if not isinstance(tid, str) or not tid:
            raise ValueError("pack.yaml tasks entries must contain task_id: <string>")
        vsel = e.get("variants")
        if vsel is None:
            out.append((tid, None))
            continue
        if not isinstance(vsel, list) or not all(isinstance(x, str) for x in vsel):
            raise ValueError(f"pack.yaml task {tid}: variants must be a list of strings")
        out.append((tid, list(vsel)))
    return out


def _expand_variants(task_yaml: Dict[str, Any]) -> List[TaskVariant]:
    task_id = str(task_yaml.get("task_id"))
    problem_slug = str(task_yaml.get("problem_slug", task_id))
    prompt = str(task_yaml.get("prompt", ""))
    variants = task_yaml.get("variants")
    if not isinstance(variants, list) or not variants:
        raise ValueError(f"Task {task_id}: variants must be a non-empty list")

    out: List[TaskVariant] = []
    for v in variants:
        if not isinstance(v, dict):
            raise ValueError(f"Task {task_id}: variant must be mapping")

        tool_delta = v.get("tool_delta")
        if tool_delta is None:
            tool_delta = {}
        if not isinstance(tool_delta, dict):
            raise ValueError(f"Task {task_id}: variant tool_delta must be a mapping")

        skill_delta = v.get("skill_delta")
        if skill_delta is None:
            skill_delta = {}
        if not isinstance(skill_delta, dict):
            raise ValueError(f"Task {task_id}: variant skill_delta must be a mapping")

        tags = v.get("tags")
        if tags is None:
            tags = []
        if not isinstance(tags, list) or not all(isinstance(x, str) for x in tags):
            raise ValueError(f"Task {task_id}: variant tags must be a list of strings")

        out.append(
            TaskVariant(
                task_id=task_id,
                problem_slug=problem_slug,
                variant_id=str(v.get("variant_id")),
                prompt=prompt,
                gptpro_hint=str(v.get("gptpro_hint", "")),
                expected=dict(v.get("expected", {})),
                tool_delta=dict(tool_delta),
                skill_delta=dict(skill_delta),
                tags=list(tags),
                fixture_overlay_dir=v.get("fixture_overlay_dir"),
            )
        )
    return out


def _select_variants(all_variants: Sequence[TaskVariant], variant_ids: Optional[List[str]], task_id: str) -> List[TaskVariant]:
    if variant_ids is None:
        return list(all_variants)
    wanted = set(variant_ids)
    selected = [tv for tv in all_variants if tv.variant_id in wanted]
    missing = wanted - {tv.variant_id for tv in selected}
    if missing:
        raise ValueError(f"pack.yaml asks for missing variants in {task_id}: {sorted(missing)}")
    return selected


def _filter_runs_by_case(runs: Sequence[TaskVariant], case_selector: Optional[str]) -> List[TaskVariant]:
    """Optionally select a single run by `<task_id>::<variant_id>`."""
    if not case_selector:
        return list(runs)

    raw = case_selector.strip()
    task_id, sep, variant_id = raw.partition("::")
    task_id = task_id.strip()
    variant_id = variant_id.strip()
    if sep != "::" or not task_id or not variant_id:
        raise ValueError("--case must be formatted as <task_id>::<variant_id>")

    selected = [tv for tv in runs if tv.task_id == task_id and tv.variant_id == variant_id]
    if selected:
        return selected

    available = sorted({f"{tv.task_id}::{tv.variant_id}" for tv in runs})
    preview = ", ".join(available[:12])
    suffix = "" if len(available) <= 12 else f" ... (+{len(available) - 12} more)"
    raise ValueError(f"--case not found: {raw}. Available cases: {preview}{suffix}")


def _copy_repo_skeleton(src_root: Path, dst_root: Path) -> None:
    """Copy repository into a fresh workspace.

    Excludes common bulky/transient directories.
    """

    def ignore(_: str, names: List[str]) -> set[str]:
        banned = {
            ".git",
            ".lake",
            "artifacts",
            "_build",
            "dist",
            "node_modules",
            ".venv",
            "__pycache__",
        }
        return {n for n in names if n in banned}

    shutil.copytree(src_root, dst_root, ignore=ignore, dirs_exist_ok=False)


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _agent_timeout_s() -> Optional[int]:
    """Agent execution timeout in seconds.

    - Default: 2400s (40m) to avoid overly aggressive timeouts.
    - LEANATLAS_AGENT_TIMEOUT_S <= 0 means no timeout.
    """
    raw = os.environ.get("LEANATLAS_AGENT_TIMEOUT_S", "").strip()
    if not raw:
        return 2400
    try:
        v = int(raw)
    except Exception:
        return 2400
    if v <= 0:
        return None
    return v


def _prune_workspace_heavy_dirs(workspace_root: Path, *, keep: bool) -> None:
    if keep:
        return
    for rel in (".lake", "build", "_lake_build"):
        p = workspace_root / rel
        if p.is_symlink() or p.is_file():
            try:
                p.unlink()
            except FileNotFoundError:
                pass
        elif p.exists():
            shutil.rmtree(p, ignore_errors=True)


def _ensure_workspace_lake_packages(src_root: Path, workspace_root: Path, *, purpose: str) -> Dict[str, Any]:
    cache = ensure_workspace_lake_packages(
        repo_root=src_root,
        workspace_root=workspace_root,
        purpose=purpose,
    )
    return cache.to_dict()




def _apply_overlay_tree(overlay_root: Path, dst_root: Path) -> None:
    """Copy overlay_root contents onto dst_root (overwrite allowed).

    Overlay roots are maintainer-provided fixture deltas. They are applied BEFORE
    the agent runs and therefore do not count as an OPERATOR patch.
    """
    if not overlay_root.exists() or not overlay_root.is_dir():
        raise FileNotFoundError(f"Overlay dir not found: {overlay_root}")

    for src in overlay_root.rglob('*'):
        if src.is_dir():
            continue
        rel = src.relative_to(overlay_root)
        dst = dst_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


_REUSE_TOOLBOX_SPECS: Dict[str, Dict[str, Any]] = {
    "mk_convex_log_barrier_gap": {
        "overlay_dirs": [
            "tests/agent_eval/scenarios/mentor_keywords_tool_reuse_v0/overlays/promote_log_barrier",
        ],
        "gate_module": "LeanAtlas.Toolbox.Convex.LogBarrier",
    },
    "mk_poly_factorization_square_dvd": {
        "overlay_dirs": [
            "tests/agent_eval/scenarios/mentor_keywords_tool_reuse_v0/overlays/promote_poly_factor",
        ],
        "gate_module": "LeanAtlas.Toolbox.Polynomial.Factorization",
    },
    "mk_poly_solvability_by_radicals_reuse": {
        "overlay_dirs": [
            "tests/agent_eval/scenarios/mentor_keywords_tool_reuse_v0/overlays/promote_solvable_by_rad",
        ],
        "gate_module": "LeanAtlas.Toolbox.FieldTheory.SolvableByRadicals",
    },
    "mk_queue_littles_law_slot_reuse": {
        "overlay_dirs": [
            "tests/agent_eval/scenarios/mentor_keywords_tool_reuse_v0/overlays/promote_little_slot",
        ],
        "gate_module": "LeanAtlas.Toolbox.Queueing.LittleSlot",
    },
    "mk_queue_mg1_lindley_reuse_nonneg": {
        "overlay_dirs": [
            "tests/agent_eval/scenarios/mentor_keywords_tool_reuse_v0/overlays/promote_lindley",
        ],
        "gate_module": "LeanAtlas.Toolbox.Queueing.Lindley",
    },
}


def _reuse_toolbox_gate_module(task_id: str) -> Optional[str]:
    spec = _REUSE_TOOLBOX_SPECS.get(task_id)
    if not isinstance(spec, dict):
        return None
    gate_module = spec.get("gate_module")
    if isinstance(gate_module, str) and gate_module:
        return gate_module
    return None


def _seed_reuse_toolbox_overlays(src_root: Path, workspace_root: Path, task_id: str) -> List[str]:
    """Materialize promoted toolbox overlays for reuse-task packs.

    Reuse tasks expect promoted `LeanAtlas/Toolbox/**` modules to exist in the
    workspace. In pack-mode runs there is no preceding scenario step to apply
    these overlays, so we seed them runner-side from explicit per-task specs.
    """
    spec = _REUSE_TOOLBOX_SPECS.get(task_id)
    if not isinstance(spec, dict):
        return []

    overlay_dirs = spec.get("overlay_dirs")
    if not isinstance(overlay_dirs, list) or not all(isinstance(x, str) for x in overlay_dirs):
        raise ValueError(f"invalid reuse overlay spec for task_id={task_id}")

    copied: List[str] = []
    for rel_dir in overlay_dirs:
        overlay = (src_root / rel_dir).resolve()
        if not overlay.exists() or not overlay.is_dir():
            raise FileNotFoundError(f"reuse overlay dir not found for task_id={task_id}: {overlay}")

        leanatlas_root = overlay / "LeanAtlas"
        if not leanatlas_root.exists() or not leanatlas_root.is_dir():
            raise FileNotFoundError(f"reuse overlay missing LeanAtlas/ for task_id={task_id}: {overlay}")

        for src in leanatlas_root.rglob("*"):
            if src.is_dir():
                continue
            rel = src.relative_to(overlay)  # keep "LeanAtlas/**" prefix
            dst = workspace_root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            copied.append(rel.as_posix())

    return sorted(set(copied))


def _run_reuse_toolbox_gate(workspace_root: Path, run_dir: Path, task_id: str, gate_module: str) -> None:
    """Fail-fast gate: seeded toolbox module must compile before running the agent."""
    gate_dir = run_dir / "ToolboxGate"
    gate_dir.mkdir(parents=True, exist_ok=True)

    res = run_cmd(
        cmd=["lake", "build", gate_module],
        cwd=workspace_root,
        log_dir=gate_dir,
        label="toolbox_gate_build",
        timeout_s=1800,
        capture_text=False,
    )

    exit_code: Optional[int] = None
    try:
        exit_code = int(res.span["exit_code"])  # type: ignore[index]
    except Exception:
        try:
            exit_code = int(res.span.exit_code)  # type: ignore[attr-defined]
        except Exception:
            exit_code = 1

    if exit_code != 0:
        raise RuntimeError(
            f"reuse toolbox gate failed for task_id={task_id}, module={gate_module}; see {gate_dir}"
        )


def _materialize_problem_fixture(fixtures_root: Path, problem_slug: str, workspace_root: Path, fixture_overlay_dir: Optional[Path] = None) -> Path:
    src = fixtures_root / "problems" / problem_slug
    if not src.exists():
        raise FileNotFoundError(f"Missing fixture for problem_slug={problem_slug}: {src}")

    dst = workspace_root / "Problems" / problem_slug
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)

    if fixture_overlay_dir is not None:
        _apply_overlay_tree(fixture_overlay_dir, dst)

    # Ensure Reports/ is empty
    reports = dst / "Reports"
    if reports.exists():
        for p in reports.iterdir():
            if p.is_file():
                p.unlink()
            else:
                shutil.rmtree(p)
    return dst


def _render_agent_prompt(tv: TaskVariant, run_id: str) -> str:
    parts: List[str] = []
    parts.append("# LeanAtlas Phase6 Agent-Eval")
    parts.append("")
    parts.append(f"Task: `{tv.task_id}`")
    parts.append(f"Variant: `{tv.variant_id}`")
    parts.append(f"Problem slug: `{tv.problem_slug}`")
    parts.append(f"Run ID (MUST use this exact folder name): `{run_id}`")
    parts.append("")
    parts.append("## Mandatory reading")
    parts.append("- `docs/agents/OPERATOR_WORKFLOW.md`")
    parts.append("- `docs/contracts/WORKFLOW_CONTRACT.md`")
    parts.append("- `docs/contracts/REPORTING_CONTRACT.md`")
    parts.append("- `docs/schemas/RunReport.schema.json`")
    parts.append("- `docs/schemas/AttemptLogLine.schema.json`")
    parts.append("")
    parts.append("## Core rules")
    parts.append("- Do not fabricate command outputs. Capture command evidence via the runner wrapper (`tools/workflow/run_cmd.py`).")
    parts.append("- Patch scope: only touch files inside `Problems/<slug>/` unless a contract explicitly allows otherwise.")
    parts.append("- Exit the proof loop only as SUCCESS or TRIAGED.")
    parts.append("- In AgentEval `--mode run`, the runner writes `pins_used.json` for grading. Do not fabricate dependency fingerprints.")
    parts.append("- Build gate policy: if `lake build Problems.<slug>.Proof` reports `unknown target`, run `lake env lean --root=. Problems/<slug>/Proof.lean`; if this fallback compile succeeds and no-sorry/verification gates pass, do not TRIAGE solely for unknown target.")
    parts.append("- Shell robustness note: under zsh, avoid assigning to reserved/read-only variable names (e.g. `status`) when generating artifacts; use safe names like `run_status`.")
    parts.append("")
    parts.append("## Task goal")
    parts.append(tv.prompt.strip())
    parts.append("")
    parts.append("## GPTPro hint")
    parts.append(tv.gptpro_hint.strip())
    parts.append("")
    parts.append("## Where to write outputs")
    parts.append(f"Write run artifacts to: `Problems/{tv.problem_slug}/Reports/{run_id}/` (see REPORTING_CONTRACT).")
    parts.append("")
    parts.append("## Expected finishing condition")
    parts.append(f"Expected final_status: `{tv.expected.get('final_status', '<missing>')}`")
    if tv.expected.get("triage_family"):
        parts.append(f"Expected triage_family: `{tv.expected.get('triage_family')}`")
    if tv.expected.get("triage_code"):
        parts.append(f"Expected triage_code: `{tv.expected.get('triage_code')}`")
    parts.append("")
    return "\n".join(parts) + "\n"


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _ensure_pins_used(report_dir: Path, workspace_root: Path) -> None:
    """Ensure AgentEval sidecar `pins_used.json` exists (runner-owned)."""
    ensure_pins_used(
        report_dir=report_dir,
        repo_root=workspace_root,
        generated_by="leanatlas.runner.agent_eval_pack",
    )


def _module_name_from_relpath(rel_lean: Path) -> str:
    """Convert a repo-relative `.lean` path to a Lean module name.

    Example: `LeanAtlas/Toolbox/Imports.lean` -> `LeanAtlas.Toolbox.Imports`.
    """
    p = rel_lean.with_suffix("")
    return ".".join(p.parts)


def _snapshot_tool_surface(workspace_root: Path) -> Dict[str, Any]:
    """Snapshot the tool-surface files/modules inside a workspace.

    This is used to deterministically evaluate `tool_delta` without needing Lean compilation:
    we compare *file presence* and (optionally) grep for expected decl names.
    """

    roots = [
        workspace_root / "LeanAtlas" / "Toolbox",
        workspace_root / "LeanAtlas" / "Incubator" / "Seeds",
        workspace_root / "LeanAtlas" / "Incubator" / "External",
    ]

    files: List[str] = []
    modules: List[str] = []
    for r in roots:
        if not r.exists():
            continue
        for p in r.rglob("*.lean"):
            try:
                rel = p.relative_to(workspace_root)
            except Exception:
                continue
            files.append(str(rel))
            modules.append(_module_name_from_relpath(rel))

    files = sorted(set(files))
    modules = sorted(set(modules))
    return {
        "schema": "leanatlas.agent_eval_tool_surface_snapshot",
        "schema_version": "0.1.0",
        "roots": ["LeanAtlas/Toolbox", "LeanAtlas/Incubator/Seeds", "LeanAtlas/Incubator/External"],
        "tool_files": files,
        "tool_modules": modules,
    }


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", required=True, help="Path to pack.yaml")
    ap.add_argument("--tasks-root", default="tests/agent_eval/tasks", help="Root for tasks")
    ap.add_argument("--fixtures-root", default="tests/agent_eval/fixtures", help="Root for fixtures")
    ap.add_argument("--out-root", default="artifacts/agent_evals", help="Where to write eval artifacts")
    ap.add_argument("--eval-id", default=None, help="Eval id (defaults to pack_id)")
    ap.add_argument(
        "--mode",
        choices=["plan", "materialize", "run"],
        default="plan",
        help="plan=validate+emit plan only; materialize=also create workspaces+prompts; run=materialize then run agent cmd",
    )
    ap.add_argument("--limit", type=int, default=None, help="Only process the first N (task,variant) runs")
    ap.add_argument(
        "--case",
        default=None,
        help="Run only one case: <task_id>::<variant_id> (keeps default full-pack behavior when omitted).",
    )
    ap.add_argument(
        "--agent-cmd",
        default=None,
        help="Shell command for running the agent non-interactively (only for --mode run).",
    )
    ap.add_argument(
        "--keep-workspace-lake",
        action="store_true",
        help="Keep workspace .lake/build directories in artifacts (default prunes them in --mode run).",
    )
    args = ap.parse_args(argv)
    keep_workspace_lake = args.keep_workspace_lake or _bool_env("LEANATLAS_KEEP_WORKSPACE_LAKE", False)

    pack_path = (REPO_ROOT / args.pack).resolve() if not os.path.isabs(args.pack) else Path(args.pack)
    tasks_root = (REPO_ROOT / args.tasks_root).resolve()
    fixtures_root = (REPO_ROOT / args.fixtures_root).resolve()
    out_root = (REPO_ROOT / args.out_root).resolve()

    pack = _load_yaml(pack_path)
    pack_id = str(pack.get("pack_id"))
    eval_id = args.eval_id or pack_id

    task_schema = _load_json_schema(SCHEMA_TASK)

    # Resolve tasks referenced by the pack
    task_refs = _discover_task_refs(pack)

    runs: List[TaskVariant] = []
    for tid, vsel in task_refs:
        task_file = tasks_root / tid / "task.yaml"
        if not task_file.exists():
            raise FileNotFoundError(f"Task not found: {task_file}")
        task_yaml = _load_yaml(task_file)
        _validate_json(task_yaml, task_schema, f"Task YAML {task_file}")
        expanded = _expand_variants(task_yaml)
        runs.extend(_select_variants(expanded, vsel, tid))

    runs = _filter_runs_by_case(runs, args.case)

    if args.limit is not None:
        runs = runs[: args.limit]

    agent_timeout_s = _agent_timeout_s()

    stamp = _utc_stamp()
    base_dir = out_root / eval_id / stamp
    base_dir.mkdir(parents=True, exist_ok=True)

    plan_runs: List[Dict[str, Any]] = []
    for tv in runs:
        run_key = f"{tv.task_id}::{tv.variant_id}"
        run_id = f"agent_eval__{tv.task_id}__{tv.variant_id}__{stamp}"[:120]
        prompt_sha = _sha256_text(tv.prompt + "\n" + tv.gptpro_hint)
        plan_runs.append(
            {
                "run_key": run_key,
                "task_id": tv.task_id,
                "variant_id": tv.variant_id,
                "problem_slug": tv.problem_slug,
                "run_id": run_id,
                "expected": tv.expected,
                "tool_delta": tv.tool_delta,
                "skill_delta": tv.skill_delta,
                "tags": tv.tags,
                "prompt_sha256": prompt_sha,
                "workspace_rel": f"runs/{tv.task_id}/{tv.variant_id}/workspace",
                "prompt_rel": f"runs/{tv.task_id}/{tv.variant_id}/PROMPT.md",
            }
        )

    plan_obj = {
        "pack_id": pack_id,
        "eval_id": eval_id,
        "stamp": stamp,
        "runs": plan_runs,
    }
    _write_json(base_dir / "Plan.json", plan_obj)

    if args.mode in ("materialize", "run"):
        for tv in runs:
            run_dir = base_dir / "runs" / tv.task_id / tv.variant_id
            ws_dir = run_dir / "workspace"
            prompt_path = run_dir / "PROMPT.md"
            try:
                if ws_dir.exists():
                    shutil.rmtree(ws_dir)

                _copy_repo_skeleton(REPO_ROOT, ws_dir)
                cache_res = _ensure_workspace_lake_packages(
                    REPO_ROOT,
                    ws_dir,
                    purpose=f"agent_eval_pack:{pack_id}:{tv.task_id}:{tv.variant_id}:materialize",
                )
                _write_json(run_dir / "CachePolicy.json", cache_res)
                if args.mode == "run" and not bool(cache_res.get("ok", False)):
                    raise RuntimeError(f"Lake package cache is not seeded: {cache_res.get('note')}")
                overlay_dir = None
                if tv.fixture_overlay_dir:
                    overlay_dir = (REPO_ROOT / tv.fixture_overlay_dir).resolve()
                _materialize_problem_fixture(fixtures_root, tv.problem_slug, ws_dir, overlay_dir)
                copied_toolbox = _seed_reuse_toolbox_overlays(REPO_ROOT, ws_dir, tv.task_id)
                gate_module = _reuse_toolbox_gate_module(tv.task_id)
                if copied_toolbox:
                    _write_json(
                        run_dir / "ToolboxSeed.json",
                        {
                            "task_id": tv.task_id,
                            "copied_files": copied_toolbox,
                            "gate_module": gate_module,
                        },
                    )
                if args.mode == "run" and copied_toolbox and gate_module:
                    _run_reuse_toolbox_gate(ws_dir, run_dir, tv.task_id, gate_module)

                # Snapshot baseline tool surface before the agent runs (deterministic grading).
                _write_json(run_dir / "BaselineToolSurface.json", _snapshot_tool_surface(ws_dir))

                run_id = f"agent_eval__{tv.task_id}__{tv.variant_id}__{stamp}"[:120]
                _write_text(prompt_path, _render_agent_prompt(tv, run_id))

                ctx = {
                    "task_id": tv.task_id,
                    "variant_id": tv.variant_id,
                    "problem_slug": tv.problem_slug,
                    "run_id": run_id,
                    "expected": tv.expected,
                    "tool_delta": tv.tool_delta,
                    "skill_delta": tv.skill_delta,
                    "tags": tv.tags,
                }
                _write_json(run_dir / "CONTEXT.json", ctx)

                if args.mode == "run":
                    if not args.agent_cmd:
                        raise ValueError("--mode run requires --agent-cmd")

                    env = os.environ.copy()
                    env["LEANATLAS_EVAL_WORKSPACE"] = str(ws_dir)
                    env["LEANATLAS_EVAL_PROMPT"] = str(prompt_path)
                    env["LEANATLAS_EVAL_RUN_ID"] = run_id

                    # Unified names (preferred): keep both for backwards-compat.
                    env["LEANATLAS_WORKSPACE"] = str(ws_dir)
                    env["LEANATLAS_PROMPT_PATH"] = str(prompt_path)
                    env["LEANATLAS_CONTEXT_PATH"] = str(run_dir / "CONTEXT.json")
                    env["LEANATLAS_RUN_ID"] = run_id
                    env["LEANATLAS_RUN_DIR"] = str(run_dir)
                    env["SHELL"] = "/bin/bash"
                    env["BASH"] = "/bin/bash"
                    env.setdefault("LEANATLAS_AGENT_SHELL", "bash")
                    env.setdefault("LEANATLAS_AGENT_TIMEOUT_S", str(agent_timeout_s or 0))

                    log_dir = run_dir / "exec_logs"
                    cache_res_run = _ensure_workspace_lake_packages(
                        REPO_ROOT,
                        ws_dir,
                        purpose=f"agent_eval_pack:{pack_id}:{tv.task_id}:{tv.variant_id}:run",
                    )
                    _write_json(run_dir / "CachePolicy.run.json", cache_res_run)
                    if not bool(cache_res_run.get("ok", False)):
                        raise RuntimeError(f"Lake package cache is not seeded: {cache_res_run.get('note')}")
                    cmd = ["bash", "-lc", args.agent_cmd]
                    res = run_cmd(
                        cmd=cmd,
                        cwd=ws_dir,
                        log_dir=log_dir,
                        label="agent",
                        env=env,
                        timeout_s=agent_timeout_s,
                        capture_text=False,
                    )
                    _write_json(run_dir / "agent_exec_span.json", res.span)

                    report_dir = ws_dir / "Problems" / tv.problem_slug / "Reports" / run_id
                    _ensure_pins_used(report_dir, ws_dir)
            finally:
                if args.mode == "run":
                    _prune_workspace_heavy_dirs(ws_dir, keep=keep_workspace_lake)

    print(f"[agent-eval] wrote: {base_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
