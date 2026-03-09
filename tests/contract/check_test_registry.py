#!/usr/bin/env python3
"""Test registry contract (core).

Goals:
1) tests/manifest.json must conform to docs/schemas/TestManifest.schema.json
2) every registered script must exist
3) every test script (by convention) must be registered
4) ids must be unique
5) Lean/Lake-executing registered tests must enforce shared Lake policy (or
   delegate to approved shared-cache runners)

Rationale: if a test isn't registered, it effectively doesn't exist for CI.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import shlex
import sys
from pathlib import Path
from typing import Any, Dict, List, Set

try:
    import jsonschema
except Exception:
    print("[test-registry] jsonschema is required. Install: pip install jsonschema", file=sys.stderr)
    raise

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "tests" / "manifest.json"
SCHEMA = ROOT / "docs" / "schemas" / "TestManifest.schema.json"

# Hard registration gate:
# Lean/Lake-executing tests must enforce shared Lake policy directly,
# or delegate to approved runner entrypoints that enforce it.
SHARED_LAKE_GUARDED_ENTRYPOINTS: Set[str] = {
    "tests/e2e/run_cases.py",
    "tests/e2e/run_scenarios.py",
    "tests/stress/soak.py",
    "tools/agent_eval/run_pack.py",
    "tools/agent_eval/run_scenario.py",
}

_DELEGATION_CALL_PREFIX = r"(?:subprocess\.(?:run|check_call|check_output|Popen|call)|run_cmd|_run)"
_SUBPROCESS_EXEC_FUNCS = {"run", "check_call", "check_output", "Popen", "call"}
_OS_EXEC_FUNCS = {"system", "popen"}
_ASYNC_EXEC_FUNCS = {"create_subprocess_exec", "create_subprocess_shell"}
_RUNNER_EXEC_FUNCS = {"run_cmd", "_run"}
_OS_IMPORT_STAR_NAMES = {"system", "popen", "execl", "execle", "execlp", "execlpe", "execv", "execve", "execvp", "execvpe"}

# Lean/Lake execution hints.
_SUBPROCESS_LAKE_OR_LEAN_LITERAL_CMD = re.compile(
    r"subprocess\.(?:run|check_call|check_output|Popen|call)\(\s*[\[\(][^\]\)]*['\"][^'\"]*\b(?:lake|lean)\b[^'\"]*['\"]",
    re.DOTALL,
)
_RUN_CMD_LAKE_OR_LEAN_LITERAL_CMD = re.compile(
    r"run_cmd\(\s*[^)]*cmd\s*=\s*[\[\(][^\]\)]*['\"][^'\"]*\b(?:lake|lean)\b[^'\"]*['\"]",
    re.DOTALL,
)
_LAKE_OR_LEAN_SHELL_CMD = re.compile(
    r"(?:subprocess\.(?:run|check_call|check_output|Popen|call)\(\s*['\"][^'\"]*\b(?:lake|lean)\b[^'\"]*['\"]"
    r"|os\.(?:system|popen)\(\s*['\"][^'\"]*\b(?:lake|lean)\b[^'\"]*['\"])",
    re.DOTALL,
)
_SUBPROCESS_OR_RUNCMD_USES_VAR = re.compile(
    r"(?:subprocess\.(?:run|check_call|check_output|Popen|call)|run_cmd|os\.(?:system|popen))\(\s*(?:args\s*=\s*|cmd\s*=\s*)?([A-Za-z_][A-Za-z0-9_]*)\b",
    re.DOTALL,
)
_HAS_EXEC_API = re.compile(
    r"\bsubprocess\.(?:run|check_call|check_output|Popen|call)\b"
    r"|\brun_cmd\("
    r"|\bos\.system\("
    r"|\bos\.popen\("
    r"|\bos\.exec[A-Za-z_]*\(",
    re.DOTALL,
)
_ASYNC_EXEC_API = re.compile(r"\basyncio\.(?:create_subprocess_exec|create_subprocess_shell)\(")
_LAKE_LEAN_TOKEN = re.compile(r"(?:^|/)(?:lake|lean)(?:$|\b)")
_SHARED_GATE_STRICT_DIRS = ("tests/e2e/", "tests/stress/")


def _parse_tree(text: str) -> ast.AST | None:
    try:
        return ast.parse(text)
    except SyntaxError:
        return None


def _attr_chain(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _attr_chain(node.value)
        if base is None:
            return None
        return f"{base}.{node.attr}"
    return None


def _latest_assignments(tree: ast.AST) -> dict[str, ast.AST]:
    latest: dict[str, tuple[int, ast.AST]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    cur = latest.get(target.id)
                    lineno = getattr(node, "lineno", 0)
                    if cur is None or lineno >= cur[0]:
                        latest[target.id] = (lineno, node.value)
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.value is not None:
                cur = latest.get(node.target.id)
                lineno = getattr(node, "lineno", 0)
                if cur is None or lineno >= cur[0]:
                    latest[node.target.id] = (lineno, node.value)
    return {name: value for name, (_, value) in latest.items()}


def _eval_string_expr(node: ast.AST, env: dict[str, ast.AST], seen: set[str]) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Constant) and isinstance(node.value, bytes):
        try:
            return node.value.decode("utf-8")
        except Exception:
            return None
    if isinstance(node, ast.Name):
        if node.id in seen:
            return None
        target = env.get(node.id)
        if target is None:
            return None
        return _eval_string_expr(target, env, seen | {node.id})
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _eval_string_expr(node.left, env, seen)
        right = _eval_string_expr(node.right, env, seen)
        if left is not None and right is not None:
            return left + right
    if isinstance(node, ast.JoinedStr):
        out: list[str] = []
        for v in node.values:
            if isinstance(v, ast.Constant) and isinstance(v.value, str):
                out.append(v.value)
                continue
            if isinstance(v, ast.FormattedValue):
                fv = _eval_string_expr(v.value, env, seen)
                if fv is None:
                    return None
                out.append(fv)
                continue
            return None
        return "".join(out)
    if isinstance(node, ast.Call):
        # Support simple dynamic string construction like ''.join(['la', 'ke']).
        fn = node.func
        if isinstance(fn, ast.Attribute) and fn.attr == "join":
            sep = _eval_string_expr(fn.value, env, seen)
            if sep is None:
                return None
            if len(node.args) != 1 or node.keywords:
                return None
            seq = node.args[0]
            if not isinstance(seq, (ast.List, ast.Tuple)):
                return None
            parts: list[str] = []
            for elt in seq.elts:
                part = _eval_string_expr(elt, env, seen)
                if part is None:
                    return None
                parts.append(part)
            return sep.join(parts)
        if isinstance(fn, ast.Attribute) and fn.attr == "replace":
            base = _eval_string_expr(fn.value, env, seen)
            if base is None:
                return None
            if len(node.args) not in {2, 3} or node.keywords:
                return None
            old = _eval_string_expr(node.args[0], env, seen)
            new = _eval_string_expr(node.args[1], env, seen)
            if old is None or new is None:
                return None
            if len(node.args) == 3:
                count_str = _eval_string_expr(node.args[2], env, seen)
                if count_str is None:
                    return None
                try:
                    return base.replace(old, new, int(count_str))
                except Exception:
                    return None
            return base.replace(old, new)
        if isinstance(fn, ast.Attribute) and fn.attr == "format":
            template = _eval_string_expr(fn.value, env, seen)
            if template is None or node.keywords:
                return None
            fmt_args: list[str] = []
            for arg in node.args:
                sval = _eval_string_expr(arg, env, seen)
                if sval is None:
                    return None
                fmt_args.append(sval)
            try:
                return template.format(*fmt_args)
            except Exception:
                return None
        # Support simple path-like command atoms, e.g. pathlib.Path('lake').
        if isinstance(fn, ast.Attribute) and fn.attr in {"Path", "PurePath", "PurePosixPath", "PureWindowsPath"}:
            if len(node.args) != 1 or node.keywords:
                return None
            return _eval_string_expr(node.args[0], env, seen)
        if isinstance(fn, ast.Name) and fn.id in {"Path", "PurePath", "PurePosixPath", "PureWindowsPath"}:
            if len(node.args) != 1 or node.keywords:
                return None
            return _eval_string_expr(node.args[0], env, seen)
    return None


def _collect_expr_tokens(
    node: ast.AST,
    *,
    env: dict[str, ast.AST],
    lit_tokens: set[str],
    name_tokens: set[str],
    seen: set[str],
) -> None:
    as_str = _eval_string_expr(node, env, seen)
    if as_str is not None:
        lit_tokens.add(as_str)
        return

    if isinstance(node, ast.Name):
        if node.id in seen:
            name_tokens.add(node.id)
            return
        target = env.get(node.id)
        if target is None:
            name_tokens.add(node.id)
            return
        _collect_expr_tokens(target, env=env, lit_tokens=lit_tokens, name_tokens=name_tokens, seen=seen | {node.id})
        return

    if isinstance(node, ast.Attribute):
        chain = _attr_chain(node)
        if chain is not None:
            name_tokens.add(chain)
        return

    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        for elt in node.elts:
            _collect_expr_tokens(elt, env=env, lit_tokens=lit_tokens, name_tokens=name_tokens, seen=seen)
        return

    if isinstance(node, ast.Starred):
        _collect_expr_tokens(node.value, env=env, lit_tokens=lit_tokens, name_tokens=name_tokens, seen=seen)
        return

    if isinstance(node, ast.Dict):
        for key in node.keys:
            if key is not None:
                _collect_expr_tokens(key, env=env, lit_tokens=lit_tokens, name_tokens=name_tokens, seen=seen)
        for val in node.values:
            _collect_expr_tokens(val, env=env, lit_tokens=lit_tokens, name_tokens=name_tokens, seen=seen)
        return


def _collect_target_names(node: ast.AST, out: set[str]) -> None:
    if isinstance(node, ast.Name):
        out.add(node.id)
        return
    if isinstance(node, (ast.Tuple, ast.List)):
        for elt in node.elts:
            _collect_target_names(elt, out)
        return
    if isinstance(node, ast.Starred):
        _collect_target_names(node.value, out)


def _collect_argument_names(args: ast.arguments, out: set[str]) -> None:
    for arg in args.posonlyargs:
        out.add(arg.arg)
    for arg in args.args:
        out.add(arg.arg)
    if args.vararg is not None:
        out.add(args.vararg.arg)
    for arg in args.kwonlyargs:
        out.add(arg.arg)
    if args.kwarg is not None:
        out.add(args.kwarg.arg)


def _var_assigned_parts(*, text: str, var_name: str) -> tuple[set[str], set[str]]:
    tree = _parse_tree(text)
    if tree is not None:
        env = _latest_assignments(tree)
        target = env.get(var_name)
        if target is not None:
            lit_tokens: set[str] = set()
            name_tokens: set[str] = set()
            _collect_expr_tokens(target, env=env, lit_tokens=lit_tokens, name_tokens=name_tokens, seen={var_name})
            return lit_tokens, name_tokens

    # Regex fallback when AST parsing is unavailable.
    pat = re.compile(rf"\b{re.escape(var_name)}\s*=\s*[\[\(]([^\]\)]*)[\]\)]", re.DOTALL)
    fallback_lit: set[str] = set()
    fallback_names: set[str] = set()
    last_body = None
    for m in pat.finditer(text):
        last_body = m.group(1)
    if last_body is None:
        return fallback_lit, fallback_names
    for tok in re.findall(r"['\"]([^'\"]+)['\"]", last_body):
        fallback_lit.add(tok)
    body_no_str = re.sub(r"['\"][^'\"]*['\"]", " ", last_body)
    for name in re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", body_no_str):
        fallback_names.add(name)
    return fallback_lit, fallback_names


def _subprocess_import_aliases(tree: ast.AST | None) -> set[str]:
    out: set[str] = set()
    if tree is None:
        return out
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.module != "subprocess":
            continue
        for alias in node.names:
            if alias.name == "*":
                out.update(_SUBPROCESS_EXEC_FUNCS)
            elif alias.name in _SUBPROCESS_EXEC_FUNCS:
                out.add(alias.asname or alias.name)
    return out


def _subprocess_module_aliases(tree: ast.AST | None) -> set[str]:
    out: set[str] = set()
    if tree is None:
        return out
    for node in ast.walk(tree):
        if not isinstance(node, ast.Import):
            continue
        for alias in node.names:
            if alias.name == "subprocess":
                out.add(alias.asname or alias.name)
    return out


def _os_module_aliases(tree: ast.AST | None) -> set[str]:
    out: set[str] = set()
    if tree is None:
        return out
    for node in ast.walk(tree):
        if not isinstance(node, ast.Import):
            continue
        for alias in node.names:
            if alias.name == "os":
                out.add(alias.asname or alias.name)
    return out


def _os_import_aliases(tree: ast.AST | None) -> set[str]:
    out: set[str] = set()
    if tree is None:
        return out
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.module != "os":
            continue
        for alias in node.names:
            if alias.name == "*":
                out.update(_OS_IMPORT_STAR_NAMES)
            elif alias.name in _OS_IMPORT_STAR_NAMES:
                out.add(alias.asname or alias.name)
    return out


def _asyncio_module_aliases(tree: ast.AST | None) -> set[str]:
    out: set[str] = set()
    if tree is None:
        return out
    for node in ast.walk(tree):
        if not isinstance(node, ast.Import):
            continue
        for alias in node.names:
            if alias.name == "asyncio":
                out.add(alias.asname or alias.name)
    return out


def _asyncio_import_aliases(tree: ast.AST | None) -> set[str]:
    out: set[str] = set()
    if tree is None:
        return out
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.module != "asyncio":
            continue
        for alias in node.names:
            if alias.name == "*":
                out.update(_ASYNC_EXEC_FUNCS)
            elif alias.name in _ASYNC_EXEC_FUNCS:
                out.add(alias.asname or alias.name)
    return out


def _expr_is_exec_callable(
    node: ast.AST,
    *,
    env: dict[str, ast.AST],
    seen: set[str],
    subprocess_import_aliases: set[str],
    subprocess_module_aliases: set[str],
    os_import_aliases: set[str],
    os_module_aliases: set[str],
    asyncio_import_aliases: set[str],
    asyncio_module_aliases: set[str],
    callable_aliases: set[str],
) -> bool:
    if isinstance(node, ast.Name):
        if (
            node.id in subprocess_import_aliases
            or node.id in os_import_aliases
            or node.id in asyncio_import_aliases
            or node.id in _RUNNER_EXEC_FUNCS
            or node.id in callable_aliases
        ):
            return True
        if node.id in seen:
            return False
        target = env.get(node.id)
        if target is None:
            return False
        return _expr_is_exec_callable(
            target,
            env=env,
            seen=seen | {node.id},
            subprocess_import_aliases=subprocess_import_aliases,
            subprocess_module_aliases=subprocess_module_aliases,
            os_import_aliases=os_import_aliases,
            os_module_aliases=os_module_aliases,
            asyncio_import_aliases=asyncio_import_aliases,
            asyncio_module_aliases=asyncio_module_aliases,
            callable_aliases=callable_aliases,
        )

    if isinstance(node, ast.Attribute):
        owner = _attr_chain(node.value)
        if owner is None:
            return False
        if node.attr in _SUBPROCESS_EXEC_FUNCS and (owner == "subprocess" or owner in subprocess_module_aliases):
            return True
        if (node.attr in _OS_EXEC_FUNCS or node.attr.startswith("exec")) and (owner == "os" or owner in os_module_aliases):
            return True
        if node.attr in _ASYNC_EXEC_FUNCS and (owner == "asyncio" or owner in asyncio_module_aliases):
            return True
        return False

    if isinstance(node, ast.Call):
        fn = node.func
        if isinstance(fn, ast.Name) and fn.id == "getattr" and len(node.args) >= 2:
            owner = _attr_chain(node.args[0])
            attr_name = _eval_string_expr(node.args[1], env, seen)
            if owner is None or attr_name is None:
                return False
            if attr_name in _SUBPROCESS_EXEC_FUNCS and (owner == "subprocess" or owner in subprocess_module_aliases):
                return True
            if (attr_name in _OS_EXEC_FUNCS or attr_name.startswith("exec")) and (owner == "os" or owner in os_module_aliases):
                return True
            if attr_name in _ASYNC_EXEC_FUNCS and (owner == "asyncio" or owner in asyncio_module_aliases):
                return True
        return False

    return False


def _collect_exec_callable_aliases(
    tree: ast.AST,
    *,
    env: dict[str, ast.AST],
    subprocess_import_aliases: set[str],
    subprocess_module_aliases: set[str],
    os_import_aliases: set[str],
    os_module_aliases: set[str],
    asyncio_import_aliases: set[str],
    asyncio_module_aliases: set[str],
) -> set[str]:
    aliases: set[str] = set()
    changed = True
    while changed:
        changed = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                value = node.value
                targets = node.targets
            elif isinstance(node, ast.AnnAssign) and node.value is not None:
                value = node.value
                targets = [node.target]
            else:
                continue
            if not _expr_is_exec_callable(
                value,
                env=env,
                seen=set(),
                subprocess_import_aliases=subprocess_import_aliases,
                subprocess_module_aliases=subprocess_module_aliases,
                os_import_aliases=os_import_aliases,
                os_module_aliases=os_module_aliases,
                asyncio_import_aliases=asyncio_import_aliases,
                asyncio_module_aliases=asyncio_module_aliases,
                callable_aliases=aliases,
            ):
                continue
            for target in targets:
                names: set[str] = set()
                _collect_target_names(target, names)
                for name in names:
                    if name not in aliases:
                        aliases.add(name)
                        changed = True
    return aliases


def _has_exec_api(text: str) -> bool:
    tree = _parse_tree(text)
    if tree is None:
        return bool(_HAS_EXEC_API.search(text) or _ASYNC_EXEC_API.search(text))

    env = _latest_assignments(tree)
    sub_import_aliases = _subprocess_import_aliases(tree)
    sub_module_aliases = _subprocess_module_aliases(tree)
    os_import_aliases = _os_import_aliases(tree)
    os_module_aliases = _os_module_aliases(tree)
    async_import_aliases = _asyncio_import_aliases(tree)
    async_module_aliases = _asyncio_module_aliases(tree)
    callable_aliases = _collect_exec_callable_aliases(
        tree,
        env=env,
        subprocess_import_aliases=sub_import_aliases,
        subprocess_module_aliases=sub_module_aliases,
        os_import_aliases=os_import_aliases,
        os_module_aliases=os_module_aliases,
        asyncio_import_aliases=async_import_aliases,
        asyncio_module_aliases=async_module_aliases,
    )

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if _expr_is_exec_callable(
            node.func,
            env=env,
            seen=set(),
            subprocess_import_aliases=sub_import_aliases,
            subprocess_module_aliases=sub_module_aliases,
            os_import_aliases=os_import_aliases,
            os_module_aliases=os_module_aliases,
            asyncio_import_aliases=async_import_aliases,
            asyncio_module_aliases=async_module_aliases,
            callable_aliases=callable_aliases,
        ):
            return True
    return False


def _token_mentions_lake_or_lean(token: str) -> bool:
    if _LAKE_LEAN_TOKEN.search(token):
        return True
    # Shell-command strings may contain multiple words, e.g. "bash -lc 'lake build'".
    if any(ch.isspace() for ch in token):
        return bool(re.search(r"\b(?:lake|lean)\b", token))
    return False


def _has_lake_or_lean_call_atoms(text: str) -> bool:
    tree = _parse_tree(text)
    if tree is None:
        return bool(re.search(r"\b(?:lake|lean)\b", text))

    env = _latest_assignments(tree)
    sub_import_aliases = _subprocess_import_aliases(tree)
    sub_module_aliases = _subprocess_module_aliases(tree)
    os_import_aliases = _os_import_aliases(tree)
    os_module_aliases = _os_module_aliases(tree)
    async_import_aliases = _asyncio_import_aliases(tree)
    async_module_aliases = _asyncio_module_aliases(tree)
    callable_aliases = _collect_exec_callable_aliases(
        tree,
        env=env,
        subprocess_import_aliases=sub_import_aliases,
        subprocess_module_aliases=sub_module_aliases,
        os_import_aliases=os_import_aliases,
        os_module_aliases=os_module_aliases,
        asyncio_import_aliases=async_import_aliases,
        asyncio_module_aliases=async_module_aliases,
    )
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        is_exec_callable = _expr_is_exec_callable(
            node.func,
            env=env,
            seen=set(),
            subprocess_import_aliases=sub_import_aliases,
            subprocess_module_aliases=sub_module_aliases,
            os_import_aliases=os_import_aliases,
            os_module_aliases=os_module_aliases,
            asyncio_import_aliases=async_import_aliases,
            asyncio_module_aliases=async_module_aliases,
            callable_aliases=callable_aliases,
        )
        is_dynamic_callable = _is_dynamic_callable_expr(node.func)
        if not is_exec_callable and not is_dynamic_callable:
            continue

        lit_tokens: set[str] = set()
        name_tokens: set[str] = set()
        for expr in _call_args_and_cmd_kwargs(node):
            _collect_expr_tokens(expr, env=env, lit_tokens=lit_tokens, name_tokens=name_tokens, seen=set())
        if any(_token_mentions_lake_or_lean(tok) for tok in lit_tokens):
            return True
        for name in name_tokens:
            more_lit, _ = _var_assigned_parts(text=text, var_name=name)
            if any(_token_mentions_lake_or_lean(tok) for tok in more_lit):
                return True
    return False


def _is_dynamic_callable_expr(node: ast.AST) -> bool:
    if isinstance(node, ast.Call):
        return True
    if isinstance(node, ast.Subscript):
        return True
    if isinstance(node, ast.Attribute) and isinstance(node.value, (ast.Call, ast.Subscript)):
        if node.attr in _SUBPROCESS_EXEC_FUNCS:
            return True
        if node.attr in _OS_EXEC_FUNCS or node.attr.startswith("exec"):
            return True
        if node.attr in _ASYNC_EXEC_FUNCS:
            return True
    return False


def _looks_like_python_launcher(token: str) -> bool:
    base = token.split("/")[-1].lower()
    if base in {"python", "python3", "uv"}:
        return True
    return base.startswith("python")


def _first_command_atom(
    node: ast.AST,
    *,
    env: dict[str, ast.AST],
    seen: set[str],
) -> tuple[str | None, str | None]:
    if isinstance(node, ast.Name):
        if node.id in seen:
            return None, node.id
        target = env.get(node.id)
        if target is None:
            return None, node.id
        return _first_command_atom(target, env=env, seen=seen | {node.id})

    if isinstance(node, (ast.List, ast.Tuple)) and node.elts:
        first = node.elts[0]
        lit = _eval_string_expr(first, env, seen)
        if lit is not None:
            return lit, None
        if isinstance(first, ast.Attribute):
            chain = _attr_chain(first)
            return None, chain
        if isinstance(first, ast.Name):
            return _first_command_atom(first, env=env, seen=seen)

    lit = _eval_string_expr(node, env, seen)
    if lit is not None:
        return lit, None
    if isinstance(node, ast.Attribute):
        return None, _attr_chain(node)
    return None, None


def _eval_command_vector(
    node: ast.AST,
    *,
    env: dict[str, ast.AST],
    seen: set[str],
) -> list[str | None] | None:
    if isinstance(node, ast.Name):
        if node.id in seen:
            return None
        target = env.get(node.id)
        if target is None:
            return None
        return _eval_command_vector(target, env=env, seen=seen | {node.id})

    if not isinstance(node, (ast.List, ast.Tuple)):
        return None

    out: list[str | None] = []
    for elt in node.elts:
        lit = _eval_string_expr(elt, env, seen)
        if lit is not None:
            out.append(lit)
            continue
        if isinstance(elt, ast.Name):
            sub_vec = _eval_command_vector(elt, env=env, seen=seen)
            if sub_vec is not None and len(sub_vec) == 1:
                out.append(sub_vec[0])
                continue
            out.append(None)
            continue
        if isinstance(elt, ast.Attribute):
            out.append(None)
            continue
        out.append(None)
    return out


def _eval_shell_command_vector(
    node: ast.AST,
    *,
    env: dict[str, ast.AST],
    seen: set[str],
) -> list[str | None] | None:
    lit = _eval_string_expr(node, env, seen)
    if lit is None:
        return None
    try:
        parts = shlex.split(lit)
    except Exception:
        parts = lit.split()
    if not parts:
        return None
    return [p for p in parts]


def _is_real_delegation_call(
    *,
    target: str,
    lit_tokens: set[str],
    name_tokens: set[str],
    first_lit: str | None,
    first_name: str | None,
    cmd_vector: list[str | None] | None,
) -> bool:
    if cmd_vector is None or target not in cmd_vector:
        return False

    idx = cmd_vector.index(target)
    first_tok = cmd_vector[0] if cmd_vector else None

    if first_tok == target:
        return True

    if first_tok is not None and _looks_like_python_launcher(first_tok):
        # Accept `python tests/e2e/run_cases.py ...`.
        if first_tok != "uv":
            return idx == 1
        # Accept `uv run python tests/e2e/run_cases.py ...`.
        if len(cmd_vector) >= 4 and cmd_vector[1] == "run":
            py_tok = cmd_vector[2]
            return py_tok is not None and _looks_like_python_launcher(py_tok) and idx == 3
        return False

    if first_name in {"sys.executable", "sys.argv[0]"} and idx == 1:
        return True

    # No trusted launcher at command head => not real delegation.
    return False


def _call_args_and_cmd_kwargs(call: ast.Call) -> list[ast.AST]:
    out: list[ast.AST] = []
    out.extend(call.args)
    for kw in call.keywords:
        if kw.arg in {"args", "cmd", None}:
            out.append(kw.value)
    return out


def _is_exec_wrapper_call(
    call: ast.Call,
    *,
    subprocess_import_aliases: set[str],
    subprocess_module_aliases: set[str],
) -> bool:
    fn = call.func
    if isinstance(fn, ast.Name):
        return fn.id in subprocess_import_aliases or fn.id in _RUNNER_EXEC_FUNCS
    if isinstance(fn, ast.Attribute):
        owner = _attr_chain(fn.value)
        if owner is None:
            return False
        if fn.attr in _SUBPROCESS_EXEC_FUNCS and (owner == "subprocess" or owner in subprocess_module_aliases):
            return True
    return False


def _has_shared_cache_ensure_call(text: str) -> bool:
    tree = _parse_tree(text)
    if tree is None:
        return False

    imported_ensure_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "tools.workflow.shared_cache":
            for alias in node.names:
                if alias.name == "ensure_workspace_lake_packages":
                    imported_ensure_names.add(alias.asname or alias.name)
    if not imported_ensure_names:
        return False

    assign_env = _latest_assignments(tree)
    shadowed: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            shadowed.add(node.name)
            _collect_argument_names(node.args, shadowed)
        elif isinstance(node, ast.Lambda):
            _collect_argument_names(node.args, shadowed)
        elif isinstance(node, ast.ClassDef):
            shadowed.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                _collect_target_names(target, shadowed)
                if isinstance(target, ast.Subscript):
                    key = _eval_string_expr(target.slice, assign_env, set())
                    if (
                        isinstance(key, str)
                        and isinstance(target.value, ast.Call)
                        and isinstance(target.value.func, ast.Name)
                        and target.value.func.id in {"globals", "locals"}
                    ):
                        shadowed.add(key)
        elif isinstance(node, ast.AnnAssign):
            _collect_target_names(node.target, shadowed)
            if isinstance(node.target, ast.Subscript):
                key = _eval_string_expr(node.target.slice, assign_env, set())
                if (
                    isinstance(key, str)
                    and isinstance(node.target.value, ast.Call)
                    and isinstance(node.target.value.func, ast.Name)
                    and node.target.value.func.id in {"globals", "locals"}
                ):
                    shadowed.add(key)
        elif isinstance(node, ast.NamedExpr):
            _collect_target_names(node.target, shadowed)
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            _collect_target_names(node.target, shadowed)
        elif isinstance(node, ast.comprehension):
            _collect_target_names(node.target, shadowed)
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                if item.optional_vars is not None:
                    _collect_target_names(item.optional_vars, shadowed)
        elif isinstance(node, ast.ExceptHandler):
            if isinstance(node.name, str):
                shadowed.add(node.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "tools.workflow.shared_cache":
                    continue
                local = alias.asname or alias.name.split(".")[0]
                shadowed.add(local)
        elif isinstance(node, ast.ImportFrom):
            trusted_shared_cache_module = (node.module == "tools.workflow")
            trusted_shared_cache_import = (node.module == "tools.workflow.shared_cache")
            for alias in node.names:
                if trusted_shared_cache_module and alias.name == "shared_cache":
                    continue
                if trusted_shared_cache_import and alias.name == "ensure_workspace_lake_packages":
                    continue
                local = alias.asname or alias.name
                shadowed.add(local)
        elif isinstance(node, ast.Call):
            # Dynamic rebinding by name should invalidate trusted-import provenance.
            if isinstance(node.func, ast.Name) and node.func.id == "setattr" and len(node.args) >= 2:
                key = _eval_string_expr(node.args[1], assign_env, set())
                if isinstance(key, str):
                    shadowed.add(key)
            elif isinstance(node.func, ast.Attribute) and node.func.attr == "__setitem__":
                owner = node.func.value
                if (
                    isinstance(owner, ast.Call)
                    and isinstance(owner.func, ast.Name)
                    and owner.func.id in {"globals", "locals"}
                    and len(node.args) >= 1
                ):
                    key = _eval_string_expr(node.args[0], assign_env, set())
                    if isinstance(key, str):
                        shadowed.add(key)

    imported_ensure_names = {n for n in imported_ensure_names if n not in shadowed}
    if not imported_ensure_names:
        return False

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if isinstance(fn, ast.Name) and fn.id in imported_ensure_names:
            return True
    return False


def _has_delegation_call(text: str) -> bool:
    tree = _parse_tree(text)
    if tree is None:
        return False

    env = _latest_assignments(tree)
    sub_import_aliases = _subprocess_import_aliases(tree)
    sub_module_aliases = _subprocess_module_aliases(tree)
    os_import_aliases = _os_import_aliases(tree)
    os_module_aliases = _os_module_aliases(tree)
    async_import_aliases = _asyncio_import_aliases(tree)
    async_module_aliases = _asyncio_module_aliases(tree)
    callable_aliases = _collect_exec_callable_aliases(
        tree,
        env=env,
        subprocess_import_aliases=sub_import_aliases,
        subprocess_module_aliases=sub_module_aliases,
        os_import_aliases=os_import_aliases,
        os_module_aliases=os_module_aliases,
        asyncio_import_aliases=async_import_aliases,
        asyncio_module_aliases=async_module_aliases,
    )

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        if not _expr_is_exec_callable(
            node.func,
            env=env,
            seen=set(),
            subprocess_import_aliases=sub_import_aliases,
            subprocess_module_aliases=sub_module_aliases,
            os_import_aliases=os_import_aliases,
            os_module_aliases=os_module_aliases,
            asyncio_import_aliases=async_import_aliases,
            asyncio_module_aliases=async_module_aliases,
            callable_aliases=callable_aliases,
        ):
            continue
        lit_tokens: set[str] = set()
        name_tokens: set[str] = set()
        for expr in _call_args_and_cmd_kwargs(node):
            _collect_expr_tokens(expr, env=env, lit_tokens=lit_tokens, name_tokens=name_tokens, seen=set())
            first_lit, first_name = _first_command_atom(expr, env=env, seen=set())
            cmd_vector = _eval_command_vector(expr, env=env, seen=set())
            if cmd_vector is None:
                cmd_vector = _eval_shell_command_vector(expr, env=env, seen=set())
            for target in SHARED_LAKE_GUARDED_ENTRYPOINTS:
                if _is_real_delegation_call(
                    target=target,
                    lit_tokens=lit_tokens,
                    name_tokens=name_tokens,
                    first_lit=first_lit,
                    first_name=first_name,
                    cmd_vector=cmd_vector,
                ):
                    return True
        for name in name_tokens:
            more_lit, _ = _var_assigned_parts(text=text, var_name=name)
            node_for_first = env.get(name)
            if node_for_first is None:
                node_for_first = ast.Name(id=name, ctx=ast.Load())
            first_lit, first_name = _first_command_atom(node_for_first, env=env, seen={name})
            cmd_vector = _eval_command_vector(node_for_first, env=env, seen={name})
            if cmd_vector is None:
                cmd_vector = _eval_shell_command_vector(node_for_first, env=env, seen={name})
            for target in SHARED_LAKE_GUARDED_ENTRYPOINTS:
                if _is_real_delegation_call(
                    target=target,
                    lit_tokens=more_lit,
                    name_tokens=name_tokens,
                    first_lit=first_lit,
                    first_name=first_name,
                    cmd_vector=cmd_vector,
                ):
                    return True
    return False


def _has_direct_lean_or_lake_exec(text: str) -> bool:
    tree = _parse_tree(text)
    if tree is not None:
        env = _latest_assignments(tree)
        sub_import_aliases = _subprocess_import_aliases(tree)
        sub_module_aliases = _subprocess_module_aliases(tree)
        os_import_aliases = _os_import_aliases(tree)
        os_module_aliases = _os_module_aliases(tree)
        async_import_aliases = _asyncio_import_aliases(tree)
        async_module_aliases = _asyncio_module_aliases(tree)
        callable_aliases = _collect_exec_callable_aliases(
            tree,
            env=env,
            subprocess_import_aliases=sub_import_aliases,
            subprocess_module_aliases=sub_module_aliases,
            os_import_aliases=os_import_aliases,
            os_module_aliases=os_module_aliases,
            asyncio_import_aliases=async_import_aliases,
            asyncio_module_aliases=async_module_aliases,
        )

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue

            is_exec_callable = _expr_is_exec_callable(
                node.func,
                env=env,
                seen=set(),
                subprocess_import_aliases=sub_import_aliases,
                subprocess_module_aliases=sub_module_aliases,
                os_import_aliases=os_import_aliases,
                os_module_aliases=os_module_aliases,
                asyncio_import_aliases=async_import_aliases,
                asyncio_module_aliases=async_module_aliases,
                callable_aliases=callable_aliases,
            )
            is_dynamic_callable = _is_dynamic_callable_expr(node.func)
            if not is_exec_callable and not is_dynamic_callable:
                continue
            args_to_scan: list[ast.AST] = _call_args_and_cmd_kwargs(node)

            lit_tokens: set[str] = set()
            name_tokens: set[str] = set()
            for expr in args_to_scan:
                _collect_expr_tokens(expr, env=env, lit_tokens=lit_tokens, name_tokens=name_tokens, seen=set())
            if any(_token_mentions_lake_or_lean(tok) for tok in lit_tokens):
                return True
            for name in name_tokens:
                more_lit, _ = _var_assigned_parts(text=text, var_name=name)
                if any(_token_mentions_lake_or_lean(tok) for tok in more_lit):
                    return True
        return False

    # Regex fallback when source cannot be parsed as AST.
    if _SUBPROCESS_LAKE_OR_LEAN_LITERAL_CMD.search(text):
        return True
    if _RUN_CMD_LAKE_OR_LEAN_LITERAL_CMD.search(text):
        return True
    if _LAKE_OR_LEAN_SHELL_CMD.search(text):
        return True
    if _ASYNC_EXEC_API.search(text) and re.search(r"\b(?:lake|lean)\b", text):
        return True
    for m in _SUBPROCESS_OR_RUNCMD_USES_VAR.finditer(text):
        var = m.group(1)
        lit_tokens, _ = _var_assigned_parts(text=text, var_name=var)
        if any(_token_mentions_lake_or_lean(tok) for tok in lit_tokens):
            return True
    return False


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def candidate_scripts() -> List[Path]:
    """Return repo-relative Paths that should be registered as tests."""
    candidates: List[Path] = []

    # Directories where every .py script (except explicit helpers) is a test.
    must_register_roots = [
        ROOT / "tests" / "contract",
        ROOT / "tests" / "schema",
        ROOT / "tests" / "determinism",
        ROOT / "tests" / "setup",
        ROOT / "tests" / "agent_eval",
        ROOT / "tests" / "e2e",
        ROOT / "tests" / "stress",
        ROOT / "tests" / "automation",
        ROOT / "tests" / "bench",
    ]

    for d in must_register_roots:
        if not d.exists():
            continue
        for p in d.rglob("*.py"):
            if p.name in {"__init__.py"}:
                continue
            candidates.append(p)

    # Exclusions: runners/helpers
    excluded_names = {
        "run.py",
        "lint.py",
        "dry_run_single.py",
    }

    out: List[Path] = []
    for p in sorted(set(candidates)):
        if p.name in excluded_names:
            continue
        # We only register tests under `tests/`.
        if "tests" not in p.parts:
            continue
        out.append(p)
    return out


def _requires_shared_lake_policy(*, script_rel: str, text: str) -> bool:
    if script_rel in SHARED_LAKE_GUARDED_ENTRYPOINTS:
        return True
    if script_rel.startswith(_SHARED_GATE_STRICT_DIRS) and _has_exec_api(text):
        return True
    # Fail closed for Lean/Lake mentions when execution APIs are present, even if
    # command atoms are dynamically shaped beyond static extraction.
    if _has_exec_api(text) and _has_lake_or_lean_call_atoms(text):
        return True
    # Delegation to guarded entrypoints still requires policy enforcement.
    if _has_delegation_call(text):
        return True
    # Direct Lean/Lake execution path.
    if _has_direct_lean_or_lake_exec(text):
        return True
    return False


def _has_shared_lake_policy(*, script_rel: str, text: str) -> bool:
    if script_rel in SHARED_LAKE_GUARDED_ENTRYPOINTS:
        return _has_shared_cache_ensure_call(text)
    # Hard rule: direct Lean/Lake execution is only allowed in approved
    # shared-cache entrypoints.
    if _has_direct_lean_or_lake_exec(text):
        return False
    if _has_shared_cache_ensure_call(text):
        return True
    # Wrapper/delegation path: invokes approved entrypoint.
    if _has_delegation_call(text):
        return True
    return False


def _run_self_tests() -> int:
    cases = [
        {
            "name": "os_popen_lake_requires_shared_policy",
            "script_rel": "tests/e2e/mock_runner.py",
            "text": "import os\nos.popen('lake env lean --version')\n",
            "expect_requires": True,
            "expect_has": False,
        },
        {
            "name": "subprocess_star_import_requires_shared_policy",
            "script_rel": "tests/stress/mock_runner.py",
            "text": "from subprocess import *\nrun(['lake', 'build'])\n",
            "expect_requires": True,
            "expect_has": False,
        },
        {
            "name": "fake_local_ensure_does_not_count",
            "script_rel": "tests/e2e/mock_runner.py",
            "text": (
                "import subprocess\n"
                "# tools.workflow.shared_cache\n"
                "def ensure_workspace_lake_packages(*args, **kwargs):\n"
                "    return None\n"
                "cmd = ['la' + 'ke', 'build']\n"
                "subprocess.run(cmd)\n"
                "ensure_workspace_lake_packages()\n"
            ),
            "expect_requires": True,
            "expect_has": False,
        },
        {
            "name": "comment_spoofed_delegation_does_not_count",
            "script_rel": "tests/e2e/mock_runner.py",
            "text": (
                "import subprocess\n"
                "cmd = ['la' + 'ke', 'build']\n"
                "subprocess.run(cmd)\n"
                "# subprocess.run(['python', 'tests/e2e/run_cases.py'])\n"
            ),
            "expect_requires": True,
            "expect_has": False,
        },
        {
            "name": "dynamic_join_lake_non_strict_still_requires_policy",
            "script_rel": "tests/contract/mock_runner.py",
            "text": "from subprocess import *\ncmd = [''.join(['la', 'ke']), 'build']\nrun(cmd)\n",
            "expect_requires": True,
            "expect_has": False,
        },
        {
            "name": "dynamic_format_lake_non_strict_requires_policy",
            "script_rel": "tests/contract/mock_runner.py",
            "text": "import subprocess\nsubprocess.run(['{}'.format('lake'), 'build'])\n",
            "expect_requires": True,
            "expect_has": False,
        },
        {
            "name": "star_args_lake_non_strict_requires_policy",
            "script_rel": "tests/contract/mock_runner.py",
            "text": "import subprocess\ncmd = ['lake', 'build']\nsubprocess.run(*(cmd,))\n",
            "expect_requires": True,
            "expect_has": False,
        },
        {
            "name": "shell_string_lake_non_strict_requires_policy",
            "script_rel": "tests/contract/mock_runner.py",
            "text": "import subprocess\nsubprocess.run(\"bash -lc 'lake build'\", shell=True)\n",
            "expect_requires": True,
            "expect_has": False,
        },
        {
            "name": "os_system_shell_lake_non_strict_requires_policy",
            "script_rel": "tests/contract/mock_runner.py",
            "text": "import os\nos.system(\"bash -lc 'lake build'\")\n",
            "expect_requires": True,
            "expect_has": False,
        },
        {
            "name": "bytes_command_atom_lake_non_strict_requires_policy",
            "script_rel": "tests/contract/mock_runner.py",
            "text": "import subprocess\nsubprocess.run([b'lake', b'build'])\n",
            "expect_requires": True,
            "expect_has": False,
        },
        {
            "name": "path_command_atom_lake_non_strict_requires_policy",
            "script_rel": "tests/contract/mock_runner.py",
            "text": "import subprocess, pathlib\nsubprocess.run([pathlib.Path('lake'), 'build'])\n",
            "expect_requires": True,
            "expect_has": False,
        },
        {
            "name": "callable_alias_exec_non_strict_requires_policy",
            "script_rel": "tests/contract/mock_runner.py",
            "text": "import subprocess\nrunner = subprocess.run\nrunner(['lake', 'build'])\n",
            "expect_requires": True,
            "expect_has": False,
        },
        {
            "name": "getattr_exec_non_strict_requires_policy",
            "script_rel": "tests/contract/mock_runner.py",
            "text": "import subprocess\ngetattr(subprocess, 'run')(['lake', 'build'])\n",
            "expect_requires": True,
            "expect_has": False,
        },
        {
            "name": "getattr_import_exec_non_strict_requires_policy",
            "script_rel": "tests/contract/mock_runner.py",
            "text": "getattr(__import__('subprocess'), 'run')(['lake', 'build'])\n",
            "expect_requires": True,
            "expect_has": False,
        },
        {
            "name": "importlib_getattr_exec_non_strict_requires_policy",
            "script_rel": "tests/contract/mock_runner.py",
            "text": "import importlib\ngetattr(importlib.import_module('subprocess'), 'run')(['lake', 'build'])\n",
            "expect_requires": True,
            "expect_has": False,
        },
        {
            "name": "globals_subprocess_getattr_non_strict_requires_policy",
            "script_rel": "tests/contract/mock_runner.py",
            "text": "import subprocess\nglobals()['subprocess'].run(['lake', 'build'])\n",
            "expect_requires": True,
            "expect_has": False,
        },
        {
            "name": "echo_target_path_is_not_real_delegation",
            "script_rel": "tests/contract/mock_runner.py",
            "text": (
                "import subprocess\n"
                "cmd = [''.join(['la', 'ke']), 'build']\n"
                "subprocess.run(cmd)\n"
                "subprocess.run(['echo', 'tests/e2e/run_cases.py'])\n"
            ),
            "expect_requires": True,
            "expect_has": False,
        },
        {
            "name": "echo_target_with_sys_executable_token_is_not_real_delegation",
            "script_rel": "tests/contract/mock_runner.py",
            "text": (
                "import subprocess, sys\n"
                "subprocess.run(['{}'.format('lake'), 'build'])\n"
                "subprocess.run(['echo', 'tests/e2e/run_cases.py', sys.executable])\n"
            ),
            "expect_requires": True,
            "expect_has": False,
        },
        {
            "name": "fake_executable_attr_is_not_real_delegation",
            "script_rel": "tests/e2e/mock_runner.py",
            "text": (
                "import subprocess\n"
                "class Fake:\n"
                "    executable = 'echo'\n"
                "f = Fake()\n"
                "subprocess.run(\"bash -lc 'lake build'\", shell=True)\n"
                "subprocess.run([f.executable, 'tests/e2e/run_cases.py'])\n"
            ),
            "expect_requires": True,
            "expect_has": False,
        },
        {
            "name": "python_c_with_target_token_is_not_real_delegation",
            "script_rel": "tests/contract/mock_runner.py",
            "text": (
                "import subprocess\n"
                "subprocess.run(['lake', 'build'])\n"
                "subprocess.run(['python', '-c', 'print(1)', 'tests/e2e/run_cases.py'])\n"
            ),
            "expect_requires": True,
            "expect_has": False,
        },
        {
            "name": "shared_cache_alias_shadowing_does_not_count",
            "script_rel": "tests/e2e/mock_runner.py",
            "text": (
                "import subprocess\n"
                "from tools.workflow import shared_cache\n"
                "class Fake:\n"
                "    def ensure_workspace_lake_packages(self):\n"
                "        return None\n"
                "shared_cache = Fake()\n"
                "subprocess.run(['lake', 'build'])\n"
                "shared_cache.ensure_workspace_lake_packages()\n"
            ),
            "expect_requires": True,
            "expect_has": False,
        },
        {
            "name": "shared_cache_attr_monkeypatch_does_not_count",
            "script_rel": "tests/e2e/mock_runner.py",
            "text": (
                "import subprocess\n"
                "from tools.workflow import shared_cache\n"
                "shared_cache.ensure_workspace_lake_packages = lambda *args, **kwargs: None\n"
                "subprocess.run(['lake', 'build'])\n"
                "shared_cache.ensure_workspace_lake_packages()\n"
            ),
            "expect_requires": True,
            "expect_has": False,
        },
        {
            "name": "shared_cache_globals_rebind_does_not_count",
            "script_rel": "tests/e2e/mock_runner.py",
            "text": (
                "import subprocess\n"
                "from tools.workflow import shared_cache\n"
                "class Fake:\n"
                "    def ensure_workspace_lake_packages(self):\n"
                "        return None\n"
                "globals()['shared_cache'] = Fake()\n"
                "subprocess.run(['lake', 'build'])\n"
                "shared_cache.ensure_workspace_lake_packages()\n"
            ),
            "expect_requires": True,
            "expect_has": False,
        },
        {
            "name": "shared_cache_param_shadowing_does_not_count",
            "script_rel": "tests/e2e/mock_runner.py",
            "text": (
                "import subprocess\n"
                "from tools.workflow import shared_cache\n"
                "def fake(shared_cache):\n"
                "    shared_cache.ensure_workspace_lake_packages()\n"
                "subprocess.run(['lake', 'build'])\n"
                "fake(object())\n"
            ),
            "expect_requires": True,
            "expect_has": False,
        },
        {
            "name": "ensure_function_param_shadowing_does_not_count",
            "script_rel": "tests/e2e/mock_runner.py",
            "text": (
                "import subprocess\n"
                "from tools.workflow.shared_cache import ensure_workspace_lake_packages\n"
                "def fake(ensure_workspace_lake_packages):\n"
                "    ensure_workspace_lake_packages()\n"
                "subprocess.run(['lake', 'build'])\n"
                "fake(lambda: None)\n"
            ),
            "expect_requires": True,
            "expect_has": False,
        },
        {
            "name": "ensure_function_globals_rebind_does_not_count",
            "script_rel": "tests/e2e/mock_runner.py",
            "text": (
                "import subprocess\n"
                "from tools.workflow.shared_cache import ensure_workspace_lake_packages\n"
                "globals()['ensure_workspace_lake_packages'] = lambda *args, **kwargs: None\n"
                "subprocess.run(['lake', 'build'])\n"
                "ensure_workspace_lake_packages()\n"
            ),
            "expect_requires": True,
            "expect_has": False,
        },
        {
            "name": "ensure_function_globals_setitem_does_not_count",
            "script_rel": "tests/e2e/mock_runner.py",
            "text": (
                "import subprocess\n"
                "from tools.workflow.shared_cache import ensure_workspace_lake_packages\n"
                "globals().__setitem__('ensure_workspace_lake_packages', lambda *args, **kwargs: None)\n"
                "subprocess.run(['lake', 'build'])\n"
                "ensure_workspace_lake_packages()\n"
            ),
            "expect_requires": True,
            "expect_has": False,
        },
        {
            "name": "ensure_function_globals_setitem_replace_does_not_count",
            "script_rel": "tests/e2e/mock_runner.py",
            "text": (
                "import subprocess\n"
                "from tools.workflow.shared_cache import ensure_workspace_lake_packages\n"
                "globals().__setitem__('ensure_workspace_lake_packages'.replace('_', '_'), lambda *args, **kwargs: None)\n"
                "subprocess.run(['lake', 'build'])\n"
                "ensure_workspace_lake_packages()\n"
            ),
            "expect_requires": True,
            "expect_has": False,
        },
        {
            "name": "ensure_function_globals_key_variable_rebind_does_not_count",
            "script_rel": "tests/e2e/mock_runner.py",
            "text": (
                "import subprocess\n"
                "from tools.workflow.shared_cache import ensure_workspace_lake_packages\n"
                "k = 'ensure_workspace_lake_packages'\n"
                "globals()[k] = lambda *args, **kwargs: None\n"
                "subprocess.run(['lake', 'build'])\n"
                "ensure_workspace_lake_packages()\n"
            ),
            "expect_requires": True,
            "expect_has": False,
        },
        {
            "name": "shared_cache_import_shadowing_does_not_count",
            "script_rel": "tests/e2e/mock_runner.py",
            "text": (
                "import subprocess\n"
                "from tools.workflow import shared_cache\n"
                "def fake():\n"
                "    import fake_shared as shared_cache\n"
                "    shared_cache.ensure_workspace_lake_packages()\n"
                "subprocess.run(['lake', 'build'])\n"
                "fake()\n"
            ),
            "expect_requires": True,
            "expect_has": False,
        },
        {
            "name": "ensure_function_import_shadowing_does_not_count",
            "script_rel": "tests/e2e/mock_runner.py",
            "text": (
                "import subprocess\n"
                "from tools.workflow.shared_cache import ensure_workspace_lake_packages\n"
                "def fake():\n"
                "    from fake_shared import ensure_workspace_lake_packages\n"
                "    ensure_workspace_lake_packages()\n"
                "subprocess.run(['lake', 'build'])\n"
                "fake()\n"
            ),
            "expect_requires": True,
            "expect_has": False,
        },
        {
            "name": "real_shared_cache_import_and_call_counts",
            "script_rel": "tests/e2e/mock_runner.py",
            "text": (
                "import subprocess\n"
                "from tools.workflow.shared_cache import ensure_workspace_lake_packages\n"
                "ensure_workspace_lake_packages()\n"
                "subprocess.run(['python', '--version'])\n"
            ),
            "expect_requires": True,
            "expect_has": True,
        },
        {
            "name": "real_delegation_counts",
            "script_rel": "tests/contract/mock_runner.py",
            "text": (
                "import subprocess\n"
                "cmd = ['python', 'tests/e2e/run_cases.py']\n"
                "subprocess.run(cmd)\n"
            ),
            "expect_requires": True,
            "expect_has": True,
        },
        {
            "name": "real_shell_string_delegation_counts",
            "script_rel": "tests/contract/mock_runner.py",
            "text": (
                "import subprocess\n"
                "subprocess.run('python tests/e2e/run_cases.py', shell=True)\n"
            ),
            "expect_requires": True,
            "expect_has": True,
        },
        {
            "name": "real_os_system_delegation_counts",
            "script_rel": "tests/contract/mock_runner.py",
            "text": (
                "import os\n"
                "os.system('python tests/e2e/run_cases.py')\n"
            ),
            "expect_requires": True,
            "expect_has": True,
        },
        {
            "name": "shell_string_echo_target_not_real_delegation",
            "script_rel": "tests/contract/mock_runner.py",
            "text": (
                "import subprocess\n"
                "subprocess.run(['lake', 'build'])\n"
                "subprocess.run('echo tests/e2e/run_cases.py', shell=True)\n"
            ),
            "expect_requires": True,
            "expect_has": False,
        },
    ]

    failures = 0
    for case in cases:
        requires = _requires_shared_lake_policy(script_rel=case["script_rel"], text=case["text"])
        has = _has_shared_lake_policy(script_rel=case["script_rel"], text=case["text"])
        if requires != case["expect_requires"] or has != case["expect_has"]:
            print(
                f"[test-registry][self-test][FAIL] {case['name']}: "
                f"requires={requires} (want {case['expect_requires']}), "
                f"has={has} (want {case['expect_has']})",
                file=sys.stderr,
            )
            failures += 1

    if failures:
        print(f"[test-registry][self-test] FAIL ({failures} case(s))", file=sys.stderr)
        return 2

    print(f"[test-registry][self-test] OK ({len(cases)} cases)")
    return 0


def _run_registry_check() -> int:
    manifest = load_json(MANIFEST)
    schema = load_json(SCHEMA)

    # 1) Schema validation
    v = jsonschema.Draft202012Validator(schema)
    errors = sorted(v.iter_errors(manifest), key=lambda e: list(e.absolute_path))
    if errors:
        print("[test-registry][FAIL] manifest schema errors:", file=sys.stderr)
        for e in errors:
            path = "/" + "/".join(str(p) for p in e.absolute_path)
            print(f"  - {path}: {e.message}", file=sys.stderr)
        return 2

    tests: List[Dict[str, Any]] = list(manifest["tests"])

    # 2) Unique ids and existing scripts
    ids: Set[str] = set()
    scripts: Set[str] = set()
    bad = 0
    bad_unshared = 0

    for t in tests:
        tid = t["id"]
        if tid in ids:
            print(f"[test-registry][FAIL] duplicate test id: {tid}", file=sys.stderr)
            bad += 1
        ids.add(tid)

        script = t["script"]
        scripts.add(script)
        sp = ROOT / script
        if not sp.exists():
            print(f"[test-registry][FAIL] missing script for {tid}: {script}", file=sys.stderr)
            bad += 1
            continue

        text = sp.read_text(encoding="utf-8", errors="replace")
        if sp.suffix != ".py":
            print(
                f"[test-registry][FAIL] UNSHARED_LEAN_LIBRARY: {script} "
                f"(registered as id={tid}, non-python scripts are not allowed by shared-Lake registration gate)",
                file=sys.stderr,
            )
            bad += 1
            bad_unshared += 1
            continue

        if _requires_shared_lake_policy(script_rel=script, text=text):
            if not _has_shared_lake_policy(script_rel=script, text=text):
                print(
                    f"[test-registry][FAIL] UNSHARED_LEAN_LIBRARY: {script} "
                    f"(registered as id={tid})",
                    file=sys.stderr,
                )
                print(
                    "[test-registry][FAIL]   missing shared Lake enforcement/delegation "
                    "(ensure_workspace_lake_packages call or approved runner invocation)",
                    file=sys.stderr,
                )
                bad += 1
                bad_unshared += 1

    # 3) Ensure all candidate scripts are registered
    missing: List[str] = []
    for p in candidate_scripts():
        rel = p.relative_to(ROOT).as_posix()
        if rel not in scripts:
            missing.append(rel)

    if missing:
        print("[test-registry][FAIL] unregistered test scripts:", file=sys.stderr)
        for m in missing:
            print(f"  - {m}", file=sys.stderr)
        bad += 1

    if bad:
        if bad_unshared:
            print(
                "[test-registry] Fix UNSHARED_LEAN_LIBRARY by routing through approved shared-cache runners "
                "or calling ensure_workspace_lake_packages directly.",
                file=sys.stderr,
            )
        print(
            "[test-registry] Fix registration issues by adding entries to tests/manifest.json "
            "and regenerating docs/testing/TEST_MATRIX.md",
            file=sys.stderr,
        )
        return 2

    print("[test-registry] OK")
    return 0


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="LeanAtlas test registry contract gate")
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run deterministic gate hardening self-tests only (no manifest scan).",
    )
    args = parser.parse_args(argv)

    if args.self_test:
        return _run_self_tests()
    return _run_registry_check()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
