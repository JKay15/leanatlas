#!/usr/bin/env python3
"""Contract: materialize smoke test must avoid shared out_root cleanup races."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "tests" / "agent_eval" / "check_runner_materialize_mode.py"


def _is_tempdir_call(node: ast.Call) -> bool:
    func = node.func
    if not isinstance(func, ast.Attribute):
        return False
    value = func.value
    if not isinstance(value, ast.Name) or value.id != "tempfile":
        return False
    return func.attr in {"TemporaryDirectory", "mkdtemp"}


def _is_shutil_rmtree_call(node: ast.Call) -> bool:
    func = node.func
    if not isinstance(func, ast.Attribute):
        return False
    value = func.value
    return isinstance(value, ast.Name) and value.id == "shutil" and func.attr == "rmtree"


def main() -> int:
    source = TARGET.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(TARGET))

    has_temp_out_root = False
    has_shutil_rmtree = False

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if _is_tempdir_call(node):
            has_temp_out_root = True
        if _is_shutil_rmtree_call(node):
            has_shutil_rmtree = True

    if not has_temp_out_root:
        print("FAIL: materialize smoke test must allocate an isolated temporary out_root")
        return 1

    if has_shutil_rmtree:
        print("FAIL: materialize smoke test must not use shared-path shutil.rmtree cleanup")
        return 1

    print("[agent-eval-materialize-out-root][PASS]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
