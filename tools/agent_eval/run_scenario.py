#!/usr/bin/env python3
"""Phase6.2 AgentEval scenario runner.

A *scenario* is a deterministic sequence of steps executed in a **shared workspace**.
It exists to test sequence effects that single-run packs cannot capture:
- interleaving TRIAGED -> maintainer patch -> SUCCESS
- regressions and recovery
- pressure (many repeats + cleanup)

This runner is deterministic except for the external agent command in `--mode run`.

Modes:
- plan: validate + expand steps, write Plan.json (and ScenarioPlan.json for backwards-compat)
- materialize: additionally create workspace + prompts/contexts (no agent execution)
- run: execute steps, including external agent for each run_task
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Ensure repo root is on sys.path so `tools.*` imports work when executed as a script.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import yaml
import jsonschema

from tools.workflow.run_cmd import run_cmd
from tools.workflow.shared_cache import ensure_workspace_lake_packages
from tools.agent_eval.pins_used import ensure_pins_used

REPO_ROOT = _REPO_ROOT
SCHEMA = json.loads((REPO_ROOT / "docs" / "schemas" / "AgentEvalScenario.schema.json").read_text(encoding="utf-8"))

TASKS_ROOT = REPO_ROOT / "tests" / "agent_eval" / "tasks"
PACKS_ROOT = REPO_ROOT / "tests" / "agent_eval" / "packs"
FIXTURES_ROOT = REPO_ROOT / "tests" / "agent_eval" / "fixtures" / "problems"


def _module_name_from_relpath(rel_lean: Path) -> str:
    """Convert a repo-relative `.lean` path to a Lean module name.

    Example: `LeanAtlas/Toolbox/Imports.lean` -> `LeanAtlas.Toolbox.Imports`.
    """
    p = rel_lean.with_suffix("")
    return ".".join(p.parts)


def _snapshot_tool_surface(workspace_root: Path) -> Dict[str, Any]:
    """Snapshot the tool-surface files/modules inside a workspace.

    Deterministic scoring uses *file/module presence* and import-graph evidence.
    This snapshot is runner-produced (not agent-produced).
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


def _write_tool_surface(step_dir: Path, workspace_root: Path) -> None:
    snap = _snapshot_tool_surface(workspace_root)
    (step_dir / "ToolSurface.json").write_text(json.dumps(snap, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _ensure_pins_used(report_dir: Path, workspace_root: Path) -> None:
    """Ensure AgentEval sidecar `pins_used.json` exists (runner-owned)."""
    ensure_pins_used(
        report_dir=report_dir,
        repo_root=workspace_root,
        generated_by="leanatlas.runner.agent_eval_scenario",
    )


def _load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _validate_schema(data: Any) -> List[str]:
    v = jsonschema.Draft202012Validator(SCHEMA)
    errs = sorted(v.iter_errors(data), key=lambda e: list(e.absolute_path))
    msgs: List[str] = []
    for e in errs:
        loc = "/" + "/".join(str(p) for p in e.absolute_path)
        msgs.append(f"{loc}: {e.message}")
    return msgs


def _sanitize_label(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9._-]+", "_", s)
    s = re.sub(r"_+", "_", s)
    return s[:80] if len(s) > 80 else s


def _copy_repo_skeleton(repo_root: Path, dst_root: Path) -> None:
    """Copy repository skeleton into dst_root, excluding artifacts/build outputs."""

    def _ignore(_dirpath: str, names: List[str]) -> set[str]:
        ignore = {
            ".git",
            ".lake",
            "build",
            "artifacts",
            "_lake_build",
            "node_modules",
            "__pycache__",
        }
        return {n for n in names if n in ignore}

    if dst_root.exists():
        shutil.rmtree(dst_root)
    shutil.copytree(repo_root, dst_root, ignore=_ignore)


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


def _apply_overlay_tree(overlay_root: Path, dst_root: Path) -> List[str]:
    """Copy overlay_root contents onto dst_root (overwrite allowed). Returns list of copied relative paths."""
    copied: List[str] = []
    if not overlay_root.exists() or not overlay_root.is_dir():
        raise FileNotFoundError(f"overlay dir not found: {overlay_root}")

    for src in overlay_root.rglob("*"):
        if src.is_dir():
            continue
        rel = src.relative_to(overlay_root)
        dst = dst_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied.append(str(rel))

    return copied


def _materialize_problem_fixture(problem_slug: str, workspace_root: Path, fixture_overlay_dir: Optional[Path] = None) -> Path:
    src = FIXTURES_ROOT / problem_slug
    if not src.exists() or not src.is_dir():
        raise FileNotFoundError(f"fixture problem not found: {src}")

    dst = workspace_root / "Problems" / problem_slug
    if dst.exists():
        shutil.rmtree(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst)

    if fixture_overlay_dir is not None:
        _apply_overlay_tree(fixture_overlay_dir, dst)

    # Ensure Reports exists and is empty.
    reports = dst / "Reports"
    if reports.exists():
        for p in reports.glob("*"):
            if p.is_file():
                p.unlink()
            else:
                shutil.rmtree(p)
    reports.mkdir(parents=True, exist_ok=True)

    return dst


def _read_task_variant(task_id: str, variant_id: str) -> Dict[str, Any]:
    task_yaml = TASKS_ROOT / task_id / "task.yaml"
    if not task_yaml.exists():
        raise FileNotFoundError(f"task.yaml not found for task_id={task_id}: {task_yaml}")
    data = _load_yaml(task_yaml)
    if not isinstance(data, dict):
        raise ValueError(f"task.yaml must be a mapping: {task_yaml}")

    problem_slug = data.get("problem_slug")
    if not isinstance(problem_slug, str):
        raise ValueError(f"task.yaml missing problem_slug: {task_yaml}")

    prompt = data.get("prompt")
    if not isinstance(prompt, str):
        prompt = ""

    keywords = data.get("keywords") if isinstance(data.get("keywords"), list) else []
    domain_hint = data.get("domain_hint") if isinstance(data.get("domain_hint"), dict) else {}

    variants = data.get("variants")
    if not isinstance(variants, list):
        raise ValueError(f"task.yaml missing variants list: {task_yaml}")

    found = None
    for v in variants:
        if isinstance(v, dict) and v.get("variant_id") == variant_id:
            found = v
            break
    if found is None:
        raise ValueError(f"variant_id '{variant_id}' not found in {task_yaml}")

    return {
        "task_id": task_id,
        "variant_id": variant_id,
        "problem_slug": problem_slug,
        "task_prompt": prompt,
        "gptpro_hint": str(found.get("gptpro_hint", "")),
        "expected": dict(found.get("expected", {})),
        "tool_delta": found.get("tool_delta", {}),
        "skill_delta": found.get("skill_delta", {}),
        "notes": str(found.get("notes", "")),
        "fixture_overlay_dir": found.get("fixture_overlay_dir"),
        "keywords": keywords,
        "domain_hint": domain_hint,
    }


def _discover_pack_task_refs(pack_yaml: Path) -> List[Dict[str, Any]]:
    data = _load_yaml(pack_yaml)
    if not isinstance(data, dict):
        raise ValueError(f"pack.yaml must be a mapping: {pack_yaml}")
    tasks = data.get("tasks")
    if not isinstance(tasks, list):
        raise ValueError(f"pack.yaml missing tasks list: {pack_yaml}")

    out: List[Dict[str, Any]] = []
    for t in tasks:
        if isinstance(t, str):
            out.append({"task_id": t})
        elif isinstance(t, dict) and isinstance(t.get("task_id"), str):
            out.append(t)
        else:
            raise ValueError(f"invalid task ref in pack.yaml: {t}")
    return out


def _list_task_variants(task_id: str) -> List[str]:
    task_yaml = TASKS_ROOT / task_id / "task.yaml"
    data = _load_yaml(task_yaml)
    if not isinstance(data, dict):
        return []
    vs = data.get("variants")
    if not isinstance(vs, list):
        return []
    out = []
    for v in vs:
        if isinstance(v, dict) and isinstance(v.get("variant_id"), str):
            out.append(v["variant_id"])
    return out


@dataclass(frozen=True)
class ExpandedStep:
    step_index: int
    kind: str
    label: str
    data: Dict[str, Any]


def _expand_steps(scenario_path: Path, scenario: Dict[str, Any]) -> List[ExpandedStep]:
    steps = scenario.get("steps")
    if not isinstance(steps, list):
        raise ValueError("scenario.steps must be a list")

    expanded: List[ExpandedStep] = []
    counter = 0

    def add(kind: str, label: str, data: Dict[str, Any]) -> None:
        nonlocal counter
        counter += 1
        expanded.append(ExpandedStep(step_index=counter, kind=kind, label=label, data=data))

    for step in steps:
        if not isinstance(step, dict):
            raise ValueError(f"invalid step (must be mapping): {step}")
        kind = step.get("kind")
        if not isinstance(kind, str):
            raise ValueError(f"step.kind must be string: {step}")

        kind_norm = kind.lower()

        if kind_norm in {"run", "run_task"}:
            task_id = step.get("task_id")
            variant_id = step.get("variant_id")
            if not isinstance(task_id, str) or not isinstance(variant_id, str):
                raise ValueError(f"run_task step requires task_id and variant_id: {step}")

            repeat = int(step.get("repeat", 1))

            reset_problem = step.get("reset_problem")
            if reset_problem is None:
                # legacy key
                if step.get("fixture_mode") == "keep":
                    reset_problem = False
                else:
                    reset_problem = True
            reset_problem = bool(reset_problem)

            base_label = step.get("label") if isinstance(step.get("label"), str) else f"{task_id}__{variant_id}"
            base_label = _sanitize_label(base_label)

            for r in range(repeat):
                suffix = f"_r{r+1}" if repeat > 1 else ""
                add(
                    "run_task",
                    base_label + suffix,
                    {
                        "task_id": task_id,
                        "variant_id": variant_id,
                        "reset_problem": reset_problem,
                        "prompt_addendum": step.get("prompt_addendum", ""),
                        "expected_override": step.get("expected_override"),
                    },
                )

        elif kind_norm == "run_pack":
            pack_id = step.get("pack_id")
            if not isinstance(pack_id, str):
                raise ValueError(f"run_pack requires pack_id: {step}")
            pack_yaml = PACKS_ROOT / pack_id / "pack.yaml"
            if not pack_yaml.exists():
                raise FileNotFoundError(f"pack.yaml not found: {pack_yaml}")

            pack_task_refs = _discover_pack_task_refs(pack_yaml)
            task_variants_override = step.get("task_variants") if isinstance(step.get("task_variants"), dict) else {}
            repeat = int(step.get("repeat", 1))

            expanded_runs: List[Tuple[str, str]] = []
            for ref in pack_task_refs:
                tid = ref.get("task_id")
                if not isinstance(tid, str):
                    continue
                variants = None
                if isinstance(ref.get("variants"), list):
                    variants = [v for v in ref.get("variants") if isinstance(v, str)]
                if variants is None:
                    variants = _list_task_variants(tid)

                if tid in task_variants_override:
                    keep = [v for v in task_variants_override[tid] if isinstance(v, str)]
                    keep_set = set(keep)
                    variants = [v for v in variants if v in keep_set]

                for vid in variants:
                    expanded_runs.append((tid, vid))

            base_label = step.get("label") if isinstance(step.get("label"), str) else f"pack__{pack_id}"
            base_label = _sanitize_label(base_label)

            for rep in range(repeat):
                rep_suffix = f"_rep{rep+1}" if repeat > 1 else ""
                for tid, vid in expanded_runs:
                    add(
                        "run_task",
                        _sanitize_label(f"{base_label}{rep_suffix}__{tid}__{vid}"),
                        {
                            "task_id": tid,
                            "variant_id": vid,
                            "reset_problem": True,
                            "prompt_addendum": step.get("prompt_addendum", ""),
                            "expected_override": step.get("expected_override"),
                            "pack_id": pack_id,
                        },
                    )

        elif kind_norm in {"maintainer_patch", "apply_overlay"}:
            overlay = step.get("overlay") or step.get("overlay_dir")
            if not isinstance(overlay, str):
                raise ValueError(f"apply_overlay requires overlay: {step}")
            mode = step.get("mode") if isinstance(step.get("mode"), str) else "MAINTAINER"
            base_label = step.get("label") if isinstance(step.get("label"), str) else "overlay"
            add("apply_overlay", _sanitize_label(base_label), {"mode": mode, "overlay": overlay})

        elif kind_norm == "clean":
            base_label = step.get("label") if isinstance(step.get("label"), str) else "clean"
            add("clean", _sanitize_label(base_label), {})

        elif kind_norm == "lake_build":
            target = step.get("target")
            if not isinstance(target, str):
                raise ValueError(f"lake_build requires target: {step}")
            base_label = step.get("label") if isinstance(step.get("label"), str) else f"lake_build_{target}"
            add("lake_build", _sanitize_label(base_label), {"target": target})

        elif kind_norm in {"run_cmd", "cmd"}:
            cmd = step.get("cmd")
            if not isinstance(cmd, list) or not all(isinstance(x, str) for x in cmd):
                raise ValueError(f"run_cmd requires cmd list: {step}")
            base_label = step.get("label") if isinstance(step.get("label"), str) else "cmd"
            add("run_cmd", _sanitize_label(base_label), {"cmd": cmd, "cwd": step.get("cwd")})

        else:
            raise ValueError(f"unknown step kind: {kind}")

    return expanded


def _mk_run_id(scenario_meta: Dict[str, Any], step: ExpandedStep, task_id: str, variant_id: str) -> str:
    return f"{scenario_meta['eval_id']}__{step.step_index:04d}__{task_id}__{variant_id}__{scenario_meta['stamp']}"


def _build_prompt(task_variant: Dict[str, Any], prompt_addendum: str, scenario_meta: Dict[str, Any], step: ExpandedStep) -> str:
    task_id = task_variant["task_id"]
    variant_id = task_variant["variant_id"]
    prompt = task_variant.get("task_prompt", "")
    hint = task_variant.get("gptpro_hint", "")

    parts: List[str] = []
    parts.append("# LeanAtlas AgentEval Scenario Run\n\n")
    parts.append(f"Scenario: `{scenario_meta['scenario_id']}` ({scenario_meta['scenario_class']})\n")
    parts.append(f"Step: {step.step_index:04d} `{step.label}`\n")
    parts.append(f"Task: `{task_id}`\n")
    parts.append(f"Variant: `{variant_id}`\n")
    parts.append("\n---\n\n")

    if prompt.strip():
        parts.append(prompt.strip() + "\n\n")

    if prompt_addendum and str(prompt_addendum).strip():
        parts.append("---\n\n")
        parts.append("## Scenario Step Addendum\n\n")
        parts.append(str(prompt_addendum).strip() + "\n\n")

    parts.append("---\n\n")
    parts.append("## Artifact note\n\n")
    parts.append("In AgentEval `--mode run`, the runner writes `pins_used.json` for grading.\n\n")
    parts.append("Build gate policy: if `lake build Problems.<slug>.Proof` reports `unknown target`, run `lake env lean --root=. Problems/<slug>/Proof.lean`; do not TRIAGE solely on unknown-target when this fallback compile + no-sorry/verification gates pass.\n\n")
    parts.append("Shell robustness note: if you write artifact scripts under zsh, do not assign to reserved/read-only names (e.g. `status`). Use safe names like `run_status`.\n\n")
    parts.append("---\n\n")
    parts.append("## GPTPro Hint\n\n")
    parts.append(hint.strip() + "\n")

    return "".join(parts)


def _write_run_files(run_dir: Path, task_variant: Dict[str, Any], scenario_meta: Dict[str, Any], step: ExpandedStep) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)

    prompt_addendum = step.data.get("prompt_addendum", "")
    (run_dir / "PROMPT.md").write_text(
        _build_prompt(task_variant, str(prompt_addendum or ""), scenario_meta, step),
        encoding="utf-8",
    )

    expected = task_variant.get("expected", {})
    if isinstance(step.data.get("expected_override"), dict):
        expected = dict(step.data["expected_override"])

    ctx = {
        "scenario_id": scenario_meta["scenario_id"],
        "scenario_class": scenario_meta["scenario_class"],
        "stamp": scenario_meta["stamp"],
        "step_index": step.step_index,
        "step_label": step.label,
        "run_id": _mk_run_id(scenario_meta, step, task_variant["task_id"], task_variant["variant_id"]),
        "task_id": task_variant["task_id"],
        "variant_id": task_variant["variant_id"],
        "problem_slug": task_variant["problem_slug"],
        "expected": expected,
        "tool_delta": task_variant.get("tool_delta", {}),
        "skill_delta": task_variant.get("skill_delta", {}),
        "notes": task_variant.get("notes", ""),
        "keywords": task_variant.get("keywords", []),
        "domain_hint": task_variant.get("domain_hint", {}),
    }

    (run_dir / "CONTEXT.json").write_text(json.dumps(ctx, indent=2) + "\n", encoding="utf-8")


def _snapshot_problem(workspace_root: Path, problem_slug: str, run_dir: Path) -> None:
    """Snapshot problem state + reports into run_dir to survive later clean/clobber steps."""
    prob = workspace_root / "Problems" / problem_slug
    if not prob.exists():
        return

    snap = run_dir / "snapshot"
    snap.mkdir(parents=True, exist_ok=True)

    # Copy reports
    reports = prob / "Reports"
    if reports.exists() and reports.is_dir():
        dst = snap / "Reports"
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(reports, dst)

    # Copy key files
    for name in ["Spec.lean", "Proof.lean", "Cache.lean", "Scratch.lean"]:
        src = prob / name
        if src.exists() and src.is_file():
            shutil.copy2(src, snap / name)


def _exec_span(
    *,
    step_dir: Path,
    cmd: List[str],
    cwd: Path,
    label: str,
    env: Optional[Dict[str, str]] = None,
    timeout_s: Optional[int] = None,
) -> Dict[str, Any]:
    """Run a command via the unified runner and return the captured exec span.

    Evidence-chain rule: spans must be written by the runner, not invented by the agent.
    """

    log_dir = step_dir / "exec_logs"
    res = run_cmd(cmd=cmd, cwd=cwd, log_dir=log_dir, label=label, env=env, timeout_s=timeout_s, capture_text=False)
    return res.span


def _run_clean(workspace_root: Path, step_dir: Path) -> None:
    """Default clean step: run scripts/clean.sh inside workspace."""
    span = _exec_span(step_dir=step_dir, cmd=["bash", "scripts/clean.sh"], cwd=workspace_root, label="clean")
    (step_dir / "clean_exec_span.json").write_text(json.dumps(span, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", required=True, help="Path to scenario.yaml")
    ap.add_argument("--eval-id", default="", help="Optional eval_id label recorded in outputs")
    ap.add_argument("--mode", required=True, choices=["plan", "materialize", "run"])
    ap.add_argument(
        "--out-root",
        default=str(REPO_ROOT / "artifacts" / "agent_evals" / "scenarios"),
        help="Output root directory",
    )
    ap.add_argument(
        "--agent-cmd",
        default="",
        help='External agent command for each run_task step (executed via `bash -lc`). Required for --mode run if scenario contains run_task steps.',
    )
    ap.add_argument(
        "--keep-workspace-lake",
        action="store_true",
        help="Keep workspace .lake/build directories in artifacts (default prunes them in --mode run).",
    )
    ap.add_argument(
        "--resume-eval-dir",
        default="",
        help="Resume an existing scenario eval dir (run mode only). Reuses workspace/runs.",
    )
    ap.add_argument(
        "--from-step",
        type=int,
        default=1,
        help="1-based expanded step index to start (or restart) from.",
    )
    ap.add_argument(
        "--reapply-overlays",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="When resuming from a later step, replay prior apply_overlay steps to reduce workspace drift.",
    )
    args = ap.parse_args()
    keep_workspace_lake = args.keep_workspace_lake or _bool_env("LEANATLAS_KEEP_WORKSPACE_LAKE", False)
    if args.from_step < 1:
        print("[scenario][FAIL] --from-step must be >= 1", file=sys.stderr)
        return 2

    scenario_path = Path(args.scenario)
    if not scenario_path.exists():
        print(f"[scenario] not found: {scenario_path}", file=sys.stderr)
        return 2

    raw = _load_yaml(scenario_path)
    errs = _validate_schema(raw)
    if errs:
        print("[scenario][FAIL] schema errors:")
        for e in errs:
            print("  ", e)
        return 1

    if not isinstance(raw, dict):
        print("[scenario] invalid scenario.yaml (must be mapping)", file=sys.stderr)
        return 2

    scenario_id = raw["scenario_id"]
    scenario_class = raw["scenario_class"]

    expanded = _expand_steps(scenario_path, raw)
    if args.from_step > len(expanded):
        print(
            f"[scenario][FAIL] --from-step={args.from_step} out of range (expanded steps={len(expanded)})",
            file=sys.stderr,
        )
        return 2

    resume_eval_dir = Path(args.resume_eval_dir).expanduser().resolve() if args.resume_eval_dir else None
    if resume_eval_dir and args.mode != "run":
        print("[scenario][FAIL] --resume-eval-dir is supported only with --mode run", file=sys.stderr)
        return 2

    if resume_eval_dir:
        eval_dir = resume_eval_dir
        if not eval_dir.exists():
            print(f"[scenario][FAIL] resume eval_dir not found: {eval_dir}", file=sys.stderr)
            return 2
        old_plan_path = eval_dir / "Plan.json"
        old_plan: Dict[str, Any] = {}
        if old_plan_path.exists():
            try:
                old_plan = json.loads(old_plan_path.read_text(encoding="utf-8"))
            except Exception as ex:
                print(f"[scenario][FAIL] cannot read existing Plan.json: {ex}", file=sys.stderr)
                return 2
            old_sid = old_plan.get("scenario_id")
            if isinstance(old_sid, str) and old_sid != scenario_id:
                print(
                    f"[scenario][FAIL] resume scenario_id mismatch: existing={old_sid} requested={scenario_id}",
                    file=sys.stderr,
                )
                return 2
        stamp = str(old_plan.get("stamp") or eval_dir.name)
        eval_id = str(old_plan.get("eval_id") or (args.eval_id if args.eval_id else f"agent_scenario__{scenario_id}"))
    else:
        stamp = _utc_stamp()
        out_root = Path(args.out_root)
        eval_dir = out_root / scenario_id / stamp
        eval_dir.mkdir(parents=True, exist_ok=True)
        eval_id = args.eval_id if args.eval_id else f"agent_scenario__{scenario_id}"

    scenario_meta = {
        "eval_id": eval_id,
        "scenario_id": scenario_id,
        "scenario_class": scenario_class,
        "scenario_path": str(scenario_path),
        "stamp": stamp,
    }

    # Keep a copy of the scenario source for self-contained grading/review.
    (eval_dir / "ScenarioSource.yaml").write_text(scenario_path.read_text(encoding="utf-8"), encoding="utf-8")

    plan = {
        "schema": "leanatlas.agent_eval_scenario_plan",
        "schema_version": "0.1.0",
        **scenario_meta,
        "steps": [
            {
                "step_index": s.step_index,
                "kind": s.kind,
                "label": s.label,
                **s.data,
            }
            for s in expanded
        ],
    }

    plan_text = json.dumps(plan, indent=2, sort_keys=True) + "\n"
    (eval_dir / "Plan.json").write_text(plan_text, encoding="utf-8")
    # Backwards-compat name (older tooling)
    (eval_dir / "ScenarioPlan.json").write_text(plan_text, encoding="utf-8")
    print(f"[scenario] wrote {eval_dir / 'Plan.json'}")

    if args.mode == "plan":
        return 0

    # Shared workspace
    workspace_root = eval_dir / "workspace"
    if resume_eval_dir:
        if not workspace_root.exists():
            print(f"[scenario][FAIL] resume workspace not found: {workspace_root}", file=sys.stderr)
            return 2
        print(f"[scenario] resuming eval_dir: {eval_dir} from step {args.from_step:04d}")
    else:
        _copy_repo_skeleton(REPO_ROOT, workspace_root)

        # Baseline tool surface for step-to-step diffs and reuse scoring.
        (eval_dir / "BaselineToolSurface.json").write_text(
            json.dumps(_snapshot_tool_surface(workspace_root), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    cache_policy = _ensure_workspace_lake_packages(
        REPO_ROOT,
        workspace_root,
        purpose=f"agent_eval_scenario:{scenario_id}:init",
    )
    (eval_dir / "CachePolicy.json").write_text(
        json.dumps(cache_policy, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if args.mode == "run" and not bool(cache_policy.get("ok", False)):
        print(f"[scenario][FAIL] Lake package cache is not seeded: {cache_policy.get('note')}", file=sys.stderr)
        return 2

    agent_timeout_s = _agent_timeout_s()

    runs_root = eval_dir / "runs"
    runs_root.mkdir(parents=True, exist_ok=True)

    # Pre-scan: do we actually need agent-cmd?
    has_run_task = any(s.kind == "run_task" for s in expanded)
    if args.mode == "run" and has_run_task and not args.agent_cmd:
        print("[scenario][FAIL] --agent-cmd required for --mode run", file=sys.stderr)
        return 2

    if resume_eval_dir and args.reapply_overlays and args.from_step > 1:
        reapplied: List[Dict[str, Any]] = []
        for s in expanded:
            if s.step_index >= args.from_step:
                break
            if s.kind != "apply_overlay":
                continue
            overlay_rel = str(s.data["overlay"])
            overlay_root = (scenario_path.parent / overlay_rel).resolve()
            copied = _apply_overlay_tree(overlay_root, workspace_root)
            reapplied.append(
                {
                    "step_index": s.step_index,
                    "label": s.label,
                    "overlay": overlay_rel,
                    "copied": copied,
                }
            )
        if reapplied:
            (eval_dir / "resume_reapply_overlays.json").write_text(
                json.dumps({"from_step": args.from_step, "applied": reapplied}, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

    try:
        for step in expanded:
            if step.step_index < args.from_step:
                continue
            if args.mode == "run":
                cache_policy_step = _ensure_workspace_lake_packages(
                    REPO_ROOT,
                    workspace_root,
                    purpose=f"agent_eval_scenario:{scenario_id}:step{step.step_index:04d}",
                )
                if not bool(cache_policy_step.get("ok", False)):
                    print(
                        f"[scenario][FAIL] Lake package cache is not seeded: {cache_policy_step.get('note')}",
                        file=sys.stderr,
                    )
                    return 2
            step_dir = runs_root / f"{step.step_index:04d}_{step.label}"
            if resume_eval_dir and step.step_index == args.from_step and step_dir.exists():
                shutil.rmtree(step_dir)
            step_dir.mkdir(parents=True, exist_ok=True)

            if step.kind == "apply_overlay":
                overlay_rel = step.data["overlay"]
                overlay_root = (scenario_path.parent / overlay_rel).resolve()
                copied = _apply_overlay_tree(overlay_root, workspace_root)
                (step_dir / "overlay_applied.json").write_text(
                    json.dumps({"overlay": overlay_rel, "copied": copied}, indent=2) + "\n",
                    encoding="utf-8",
                )
                _write_tool_surface(step_dir, workspace_root)
                continue

            if step.kind == "clean":
                _run_clean(workspace_root, step_dir)
                _write_tool_surface(step_dir, workspace_root)
                continue

            if step.kind == "lake_build":
                target = step.data["target"]
                if args.mode == "run":
                    span = _exec_span(
                        step_dir=step_dir,
                        cmd=["bash", "-lc", f"lake build {target}"],
                        cwd=workspace_root,
                        label="lake_build",
                    )
                    (step_dir / "lake_build_exec_span.json").write_text(
                        json.dumps(span, indent=2, sort_keys=True) + "\n", encoding="utf-8"
                    )
                else:
                    (step_dir / "lake_build_pending.json").write_text(json.dumps({"target": target}, indent=2) + "\n", encoding="utf-8")
                _write_tool_surface(step_dir, workspace_root)
                continue

            if step.kind == "run_cmd":
                if args.mode == "run":
                    cmd = step.data["cmd"]
                    cwd = step.data.get("cwd")
                    cwd_path = workspace_root
                    if isinstance(cwd, str) and cwd.strip():
                        cwd_path = (workspace_root / cwd).resolve()
                    span = _exec_span(step_dir=step_dir, cmd=cmd, cwd=cwd_path, label="cmd")
                    (step_dir / "cmd_exec_span.json").write_text(
                        json.dumps(span, indent=2, sort_keys=True) + "\n", encoding="utf-8"
                    )
                else:
                    (step_dir / "cmd_pending.json").write_text(json.dumps(step.data, indent=2) + "\n", encoding="utf-8")
                _write_tool_surface(step_dir, workspace_root)
                continue

            if step.kind != "run_task":
                (step_dir / "skipped.json").write_text(json.dumps({"reason": "unknown step kind"}, indent=2) + "\n", encoding="utf-8")
                _write_tool_surface(step_dir, workspace_root)
                continue

            # run_task
            task_id = step.data["task_id"]
            variant_id = step.data["variant_id"]
            tv = _read_task_variant(task_id, variant_id)

            reset = bool(step.data.get("reset_problem", True))

            overlay_dir = None
            if reset and tv.get("fixture_overlay_dir"):
                overlay_dir = (REPO_ROOT / str(tv["fixture_overlay_dir"])).resolve()

            if reset:
                _materialize_problem_fixture(tv["problem_slug"], workspace_root, overlay_dir)
            else:
                # Ensure Reports exists.
                (workspace_root / "Problems" / tv["problem_slug"] / "Reports").mkdir(parents=True, exist_ok=True)

            _write_run_files(step_dir, tv, scenario_meta, step)

            # Tool-surface snapshot at the end of materialization (before any agent run).
            # In --mode run, this will be overwritten after the agent runs.
            _write_tool_surface(step_dir, workspace_root)

            if args.mode != "run":
                continue

            run_id = _mk_run_id(scenario_meta, step, task_id, variant_id)

            env = dict(os.environ)
            env["LEANATLAS_WORKSPACE"] = str(workspace_root)
            env["LEANATLAS_PROMPT_PATH"] = str(step_dir / "PROMPT.md")
            env["LEANATLAS_CONTEXT_PATH"] = str(step_dir / "CONTEXT.json")
            env["LEANATLAS_RUN_DIR"] = str(step_dir)
            env["LEANATLAS_RUN_ID"] = run_id
            env["LEANATLAS_SCENARIO_ID"] = scenario_id
            env["LEANATLAS_SCENARIO_CLASS"] = scenario_class
            env["LEANATLAS_SCENARIO_STEP"] = str(step.step_index)
            env["SHELL"] = "/bin/bash"
            env["BASH"] = "/bin/bash"
            env.setdefault("LEANATLAS_AGENT_SHELL", "bash")
            env.setdefault("LEANATLAS_AGENT_TIMEOUT_S", str(agent_timeout_s or 0))

            span = _exec_span(
                step_dir=step_dir,
                cmd=["bash", "-lc", args.agent_cmd],
                cwd=workspace_root,
                label="agent",
                env=env,
                timeout_s=agent_timeout_s,
            )
            (step_dir / "agent_exec_span.json").write_text(json.dumps(span, indent=2, sort_keys=True) + "\n", encoding="utf-8")

            report_dir = workspace_root / "Problems" / tv["problem_slug"] / "Reports" / run_id
            _ensure_pins_used(report_dir, workspace_root)

            # Snapshot for grading.
            _snapshot_problem(workspace_root, tv["problem_slug"], step_dir)

            # Tool-surface snapshot after the agent run (for step-to-step diffs and reuse scoring).
            _write_tool_surface(step_dir, workspace_root)
    finally:
        if args.mode == "run":
            _prune_workspace_heavy_dirs(workspace_root, keep=keep_workspace_lake)

    print(f"[scenario] eval_dir: {eval_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
