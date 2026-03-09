#!/usr/bin/env python3
"""Contract: in-repo LOOP library facade and generic skills/docs routing must exist."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _fail(msg: str) -> int:
    print(f"[loop-library-packaging][FAIL] {msg}", file=sys.stderr)
    return 2


def _read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise FileNotFoundError(rel)
    return path.read_text(encoding="utf-8")


def main() -> int:
    try:
        from looplib import (
            LoopGraphRuntime,
            build_default_review_orchestration_bundle,
            issue_root_supervisor_exception,
            materialize_batch_supervisor,
            publish_capability_event,
            publish_supervisor_guidance_event,
        )
    except Exception as exc:  # noqa: BLE001
        return _fail(f"looplib import surface is not available: {exc}")

    if not callable(build_default_review_orchestration_bundle):
        return _fail("looplib must expose build_default_review_orchestration_bundle")
    if not callable(materialize_batch_supervisor):
        return _fail("looplib must expose materialize_batch_supervisor")
    if not callable(issue_root_supervisor_exception):
        return _fail("looplib must expose issue_root_supervisor_exception")
    if not callable(publish_capability_event):
        return _fail("looplib must expose publish_capability_event")
    if not callable(publish_supervisor_guidance_event):
        return _fail("looplib must expose publish_supervisor_guidance_event")
    if LoopGraphRuntime.__name__ != "LoopGraphRuntime":
        return _fail("looplib must expose the role-neutral graph runtime class")
    import_probe = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import builtins\n"
                "orig = builtins.__import__\n"
                "def guarded(name, globals=None, locals=None, fromlist=(), level=0):\n"
                "    if name == 'tools.workflow.run_cmd':\n"
                "        raise ModuleNotFoundError('blocked tools.workflow.run_cmd for looplib packaging test')\n"
                "    return orig(name, globals, locals, fromlist, level)\n"
                "builtins.__import__ = guarded\n"
                "from looplib import execute_batch_supervisor, materialize_batch_supervisor\n"
                "print(callable(execute_batch_supervisor) and callable(materialize_batch_supervisor))\n"
            ),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if import_probe.returncode != 0:
        return _fail(
            "looplib batch-supervisor imports must not require tools.workflow.run_cmd at import time: "
            + (import_probe.stderr.strip() or import_probe.stdout.strip())
        )
    if import_probe.stdout.strip() != "True":
        return _fail("looplib batch-supervisor imports must remain callable when host-only worktree helpers are unavailable")

    quickstart_rel = "docs/setup/LOOP_LIBRARY_QUICKSTART.md"
    example_rel = "examples/looplib_quickstart.py"
    generic_skill_rels = [
        ".agents/skills/loop-mainline/SKILL.md",
        ".agents/skills/loop-review-orchestration/SKILL.md",
        ".agents/skills/loop-batch-supervisor/SKILL.md",
    ]
    generic_doc_surfaces = {
        quickstart_rel: [
            "looplib",
            ".agents/skills/loop-mainline/SKILL.md",
            ".agents/skills/loop-review-orchestration/SKILL.md",
            ".agents/skills/loop-batch-supervisor/SKILL.md",
            "root supervisor kernel",
            "root_supervisor_skeleton.json",
            "issue_root_supervisor_exception(...)",
            "MaintainerLoopSession",
            "session.run_key",
            "reusable in-repo",
            "external-repository/non-LeanAtlas packaging is tracked separately",
        ],
        "docs/agents/LOOP_MAINLINE.md": [
            "looplib",
            ".agents/skills/loop-mainline/SKILL.md",
            ".agents/skills/loop-review-orchestration/SKILL.md",
            ".agents/skills/loop-batch-supervisor/SKILL.md",
            "root supervisor kernel",
        ],
        "docs/agents/README.md": [
            quickstart_rel,
            ".agents/skills/loop-mainline/SKILL.md",
        ],
    }

    for rel, snippets in generic_doc_surfaces.items():
        text = _read(rel)
        for snippet in snippets:
            if snippet not in text:
                return _fail(f"{rel} missing required snippet `{snippet}`")
    if "\"f\" * 64" in _read(quickstart_rel):
        return _fail(f"{quickstart_rel} must not demonstrate issue_root_supervisor_exception(...) with a dummy run_key")

    example = _read(example_rel)
    if "import looplib" not in example and "from looplib import" not in example:
        return _fail(f"{example_rel} must demonstrate looplib imports")

    skills_index = _read(".agents/skills/README.md")
    for skill_rel in generic_skill_rels:
        skill_text = _read(skill_rel)
        if "Outputs" not in skill_text or "Must-run checks" not in skill_text:
            return _fail(f"{skill_rel} must follow the standard skill header contract")
        if skill_rel not in skills_index:
            return _fail(f".agents/skills/README.md must index {skill_rel}")
    if "root supervisor kernel" not in _read(".agents/skills/loop-mainline/SKILL.md"):
        return _fail(".agents/skills/loop-mainline/SKILL.md must explain the root supervisor kernel route")
    if "layered supervisor" not in _read(".agents/skills/loop-batch-supervisor/SKILL.md"):
        return _fail(".agents/skills/loop-batch-supervisor/SKILL.md must explain layered supervisors explicitly")

    print("[loop-library-packaging] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
