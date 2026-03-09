#!/usr/bin/env python3
"""Contract: phase-1 owner inversion must move generic preference policy into looplib."""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _fail(msg: str) -> int:
    print(f"[loop-library-ownership-boundary][FAIL] {msg}", file=sys.stderr)
    return 2


def _read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise FileNotFoundError(rel)
    return path.read_text(encoding="utf-8")


def main() -> int:
    try:
        from looplib.preferences import build_default_review_policy
    except Exception as exc:  # noqa: BLE001
        return _fail(f"looplib.preferences must exist as a library-owned policy module: {exc}")

    policy = build_default_review_policy()
    if policy.get("assurance_preset") != "Budget Saver":
        return _fail("looplib.preferences must preserve the committed default preference policy")
    if policy.get("review_tier_policy") != "LOW_PLUS_MEDIUM":
        return _fail("looplib.preferences must preserve the committed default review tier policy")

    module_text = _read("looplib/preferences.py")
    if ".cache/leanatlas/onboarding/loop_preferences.json" in module_text:
        return _fail("looplib.preferences must not embed LeanAtlas-local artifact path semantics")
    if "DEFAULT_PREFERENCE_ARTIFACT_REL" in module_text:
        return _fail("looplib.preferences must not own the LeanAtlas artifact path constant")

    review_text = _read("looplib/review.py")
    review_ast = ast.parse(review_text, filename="looplib/review.py")
    imports_build_default_from_preferences = False
    imports_build_default_from_tools = False
    for node in ast.walk(review_ast):
        if not isinstance(node, ast.ImportFrom):
            continue
        module = node.module or ""
        imported_names = {alias.name for alias in node.names}
        if module == "preferences" and node.level == 1 and "build_default_review_policy" in imported_names:
            imports_build_default_from_preferences = True
        if module == "tools.loop" and "build_default_review_policy" in imported_names:
            imports_build_default_from_tools = True
    if not imports_build_default_from_preferences:
        return _fail("looplib.review must source build_default_review_policy from looplib.preferences")
    if imports_build_default_from_tools:
        return _fail("looplib.review must not source build_default_review_policy from tools.loop")

    user_pref_text = _read("tools/loop/user_preferences.py")
    if ".cache/leanatlas/onboarding/loop_preferences.json" not in user_pref_text:
        return _fail("tools.loop.user_preferences must remain the LeanAtlas artifact-path adapter")
    if "from looplib.preferences import" not in user_pref_text:
        return _fail("tools.loop.user_preferences must delegate generic policy logic to looplib.preferences")

    import_probe = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import builtins\n"
                "orig = builtins.__import__\n"
                "def guarded(name, globals=None, locals=None, fromlist=(), level=0):\n"
                "    if name == 'tools.loop' or name.endswith('user_preferences'):\n"
                "        raise ModuleNotFoundError(f'blocked {name} for owner-boundary test')\n"
                "    return orig(name, globals, locals, fromlist, level)\n"
                "builtins.__import__ = guarded\n"
                "from looplib.preferences import build_default_review_policy\n"
                "print(build_default_review_policy()['review_tier_policy'])\n"
            ),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if import_probe.returncode != 0:
        return _fail(
            "looplib.preferences must be importable even when tools.loop.user_preferences is unavailable: "
            + (import_probe.stderr.strip() or import_probe.stdout.strip())
        )
    if import_probe.stdout.strip() != "LOW_PLUS_MEDIUM":
        return _fail("looplib.preferences import probe returned an unexpected review tier policy")

    root_export_probe = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import builtins\n"
                "orig = builtins.__import__\n"
                "def guarded(name, globals=None, locals=None, fromlist=(), level=0):\n"
                "    if name == 'tools.loop' or name.endswith('user_preferences'):\n"
                "        raise ModuleNotFoundError(f'blocked {name} for owner-boundary test')\n"
                "    return orig(name, globals, locals, fromlist, level)\n"
                "builtins.__import__ = guarded\n"
                "from looplib import build_default_review_policy\n"
                "print(build_default_review_policy()['assurance_preset'])\n"
            ),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if root_export_probe.returncode != 0:
        return _fail(
            "looplib root export must resolve build_default_review_policy without importing tools.loop: "
            + (root_export_probe.stderr.strip() or root_export_probe.stdout.strip())
        )
    if root_export_probe.stdout.strip() != "Budget Saver":
        return _fail("looplib root export probe returned an unexpected assurance preset")

    print("[loop-library-ownership-boundary] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
