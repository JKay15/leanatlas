#!/usr/bin/env python3
"""Generate docs/setup/TEST_ENV_INVENTORY.md from repository sources.

Goal: keep a deterministic, auditable inventory of environment requirements
that appear in test codepaths (tests/, tools/, scripts/).
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import DefaultDict, Iterable, List, Set

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "setup" / "TEST_ENV_INVENTORY.md"
SCAN_ROOTS = (ROOT / "tests", ROOT / "tools", ROOT / "scripts")

LEA_ENV_RE = re.compile(r"\bLEANATLAS_[A-Z0-9_]+\b")
LIST_CMD_RE = re.compile(
    r"(?:cmd\s*=|['\"]cmd['\"]\s*:)\s*\[\s*['\"]([A-Za-z0-9._+-]+)['\"]"
)
CMD_DEFAULT_RE = re.compile(r"(?:_CMD|_COMMAND)\s*=\s*\"[^\"]*:-([A-Za-z0-9._+-]+)\}?\"")

SHELL_SKIP = {
    "if",
    "then",
    "elif",
    "else",
    "fi",
    "for",
    "do",
    "done",
    "while",
    "case",
    "esac",
    "in",
    "function",
    "local",
    "export",
    "readonly",
    "return",
    "exit",
    "break",
    "continue",
    "set",
    "source",
    ".",
    "shift",
    "printf",
    "echo",
    "read",
    "test",
    "[",
    "[[",
    "{",
    "}",
}

KNOWN_COMMAND_ALLOW = {
    "bash",
    "claude",
    "codex",
    "domain-mcp",
    "git",
    "lake",
    "python",
    "python3",
    "pre-commit",
    "rg",
    "uv",
    "uvx",
}

EXTERNAL_BY_DEFAULT = {"jsonschema", "yaml", "drain3"}


def _rel(p: Path) -> str:
    return str(p.relative_to(ROOT))


def _add(dst: DefaultDict[str, Set[str]], key: str, path: Path) -> None:
    k = key.strip()
    if not k:
        return
    dst[k].add(_rel(path))


def _stdlib() -> Set[str]:
    std = getattr(sys, "stdlib_module_names", None)
    if std is None:
        return set()
    return set(std)


def _iter_files() -> Iterable[Path]:
    exts = {".py", ".sh"}
    this_file = Path(__file__).resolve()
    for root in SCAN_ROOTS:
        if not root.exists():
            continue
        for p in sorted(root.rglob("*")):
            if p.resolve() == this_file:
                continue
            if p.is_file() and p.suffix in exts:
                yield p


def _scan_python(
    path: Path,
    text: str,
    cmd_hits: DefaultDict[str, Set[str]],
    env_hits: DefaultDict[str, Set[str]],
    import_hits: DefaultDict[str, Set[str]],
) -> None:
    for env_name in LEA_ENV_RE.findall(text):
        _add(env_hits, env_name, path)

    for cmd in LIST_CMD_RE.findall(text):
        _add(cmd_hits, cmd, path)

    if "codex exec" in text:
        _add(cmd_hits, "codex", path)
    if "claude exec" in text:
        _add(cmd_hits, "claude", path)

    try:
        tree = ast.parse(text)
    except SyntaxError:
        return

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                mod = alias.name.split(".", 1)[0]
                _add(import_hits, mod, path)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                mod = node.module.split(".", 1)[0]
                _add(import_hits, mod, path)

        if not isinstance(node, ast.Call):
            continue

        fn = node.func
        if isinstance(fn, ast.Attribute) and fn.attr == "which" and node.args:
            a0 = node.args[0]
            if isinstance(a0, ast.Constant) and isinstance(a0.value, str):
                _add(cmd_hits, a0.value, path)

        call_attr = fn.attr if isinstance(fn, ast.Attribute) else ""
        if call_attr not in {"run", "Popen", "call", "check_call", "check_output"}:
            continue

        arg0 = None
        if node.args:
            arg0 = node.args[0]
        else:
            for kw in node.keywords:
                if kw.arg in {"args", "cmd", "command"}:
                    arg0 = kw.value
                    break

        if isinstance(arg0, (ast.List, ast.Tuple)) and arg0.elts:
            first = arg0.elts[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                _add(cmd_hits, first.value, path)


def _scan_shell(
    path: Path,
    text: str,
    cmd_hits: DefaultDict[str, Set[str]],
    env_hits: DefaultDict[str, Set[str]],
) -> None:
    for env_name in LEA_ENV_RE.findall(text):
        _add(env_hits, env_name, path)

    for m in re.finditer(r"command\s+-v\s+([A-Za-z0-9._+-]+)", text):
        _add(cmd_hits, m.group(1), path)

    for m in CMD_DEFAULT_RE.finditer(text):
        _add(cmd_hits, m.group(1), path)

    if "codex exec" in text:
        _add(cmd_hits, "codex", path)
    if "claude exec" in text:
        _add(cmd_hits, "claude", path)

    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line.split(" ", 1)[0]:
            continue
        token = line.split()[0]
        token = token.split("/", 1)[0]
        if token in SHELL_SKIP:
            continue
        if token in KNOWN_COMMAND_ALLOW:
            _add(cmd_hits, token, path)


def _normalize_cmds(cmd_hits: DefaultDict[str, Set[str]]) -> DefaultDict[str, Set[str]]:
    out: DefaultDict[str, Set[str]] = defaultdict(set)
    aliases = {"python3": "python"}
    for cmd, paths in cmd_hits.items():
        c = aliases.get(cmd, cmd)
        if c in KNOWN_COMMAND_ALLOW:
            out[c].update(paths)
    return out


def _normalize_imports(import_hits: DefaultDict[str, Set[str]]) -> DefaultDict[str, Set[str]]:
    std = _stdlib()
    out: DefaultDict[str, Set[str]] = defaultdict(set)
    for mod, paths in import_hits.items():
        if mod in {"tests", "tools", "scripts", "docs", "typing_extensions"}:
            continue
        if mod in std:
            continue
        if mod.startswith("_"):
            continue
        if mod in EXTERNAL_BY_DEFAULT:
            out[mod].update(paths)
    return out


def _render(cmds: DefaultDict[str, Set[str]], envs: DefaultDict[str, Set[str]], imports: DefaultDict[str, Set[str]]) -> str:
    lines: List[str] = []
    lines.append("# Test Environment Inventory\n\n")
    lines.append(
        "> Deterministic inventory generated from `tests/`, `tools/`, and `scripts/` by "
        "`uv run --locked python tools/tests/generate_test_env_inventory.py --write`.\n"
    )
    lines.append("> Scope: environment requirements that appear in test and test-runner codepaths.\n\n")

    lines.append("## External Commands Referenced by Tests\n\n")
    lines.append("| Command | Role | Evidence (files) |\n")
    lines.append("|---|---|---|\n")

    role = {
        "python": "Primary runtime for all registered tests and tooling.",
        "pre-commit": "Repo-local git hooks and commit/branch policy enforcement.",
        "uv": "Locked Python environment sync/check path.",
        "uvx": "Pinned external tool execution (MCP checks).",
        "lake": "Lean build/lint/test execution and cache warmup.",
        "rg": "Fast fallback search backend (recommended).",
        "bash": "Runner shell for scripted scenario and agent commands.",
        "claude": "Supported real-agent CLI backend (claude exec).",
        "codex": "Supported real-agent CLI backend (codex exec).",
        "domain-mcp": "Domain MCP CLI endpoint (default command name).",
        "git": "Repository metadata checks in tests/contracts.",
    }

    for cmd in sorted(cmds):
        ev = ", ".join(f"`{p}`" for p in sorted(cmds[cmd])[:8])
        if len(cmds[cmd]) > 8:
            ev += ", ..."
        lines.append(f"| `{cmd}` | {role.get(cmd, 'Referenced in test codepaths.')} | {ev} |\n")

    lines.append("\n")
    lines.append("## Third-Party Python Modules Referenced\n\n")
    lines.append("| Module | Role | Evidence (files) |\n")
    lines.append("|---|---|---|\n")

    import_role = {
        "jsonschema": "Schema validation for contracts and fixtures.",
        "yaml": "YAML parsing for test manifests/scenarios/tasks.",
        "drain3": "Telemetry/log pattern mining checks.",
    }

    for mod in sorted(imports):
        ev = ", ".join(f"`{p}`" for p in sorted(imports[mod])[:8])
        if len(imports[mod]) > 8:
            ev += ", ..."
        lines.append(f"| `{mod}` | {import_role.get(mod, 'Referenced by test codepaths.')} | {ev} |\n")

    lines.append("\n")
    lines.append("## LEANATLAS Environment Variables Observed\n\n")
    lines.append("| Variable | Purpose Category | Evidence (files) |\n")
    lines.append("|---|---|---|\n")

    def cat(name: str) -> str:
        if name in {
            "LEANATLAS_REAL_AGENT_CMD",
            "LEANATLAS_REAL_AGENT_PROVIDER",
            "LEANATLAS_REAL_AGENT_PROFILE",
            "LEANATLAS_AGENT_TIMEOUT_S",
            "LEANATLAS_AGENT_SHELL",
        }:
            return "Real-agent execution"
        if name.startswith("LEANATLAS_DOMAIN_MCP"):
            return "Domain MCP installation/command"
        if name in {"LEANATLAS_SHARED_LAKE_PACKAGES", "LEANATLAS_LAKE_PACKAGES_SEED_FROM", "LEANATLAS_ALLOW_HEAVY_PACKAGE_COPY", "LEANATLAS_KEEP_WORKSPACE_LAKE"}:
            return "Shared Lake cache policy"
        if "SCENARIO" in name:
            return "Scenario runtime context"
        if name in {"LEANATLAS_WORKSPACE", "LEANATLAS_EVAL_WORKSPACE", "LEANATLAS_E2E_WORKDIR"}:
            return "Workspace routing"
        if name in {"LEANATLAS_PROMPT_PATH", "LEANATLAS_EVAL_PROMPT", "LEANATLAS_CONTEXT_PATH", "LEANATLAS_EVAL_CONTEXT"}:
            return "Prompt/context handoff"
        if name in {"LEANATLAS_RUN_ID", "LEANATLAS_EVAL_RUN_ID", "LEANATLAS_RUN_DIR", "LEANATLAS_SESSION_ID", "LEANATLAS_AGENT_BUILD_ID"}:
            return "Traceability/telemetry"
        if name == "LEANATLAS_STRICT_DEPS":
            return "Strict dependency smoke"
        return "Runtime policy"

    for env in sorted(envs):
        ev = ", ".join(f"`{p}`" for p in sorted(envs[env])[:8])
        if len(envs[env]) > 8:
            ev += ", ..."
        lines.append(f"| `{env}` | {cat(env)} | {ev} |\n")

    lines.append("\n")
    lines.append("## Operational Notes\n\n")
    lines.append("- Core profile can run without real-agent config, but nightly real-agent tests require either `LEANATLAS_REAL_AGENT_PROVIDER` (optional profile) or `LEANATLAS_REAL_AGENT_CMD`.\n")
    lines.append("- Shared Lake policy is enforced by `tests/contract/check_shared_cache_policy.py`; runners must hydrate workspace `.lake/packages` via shared cache.\n")
    lines.append("- MCP tools are external installs: `lean-lsp-mcp` (third-party) and `lean-domain-mcp` (Repo C command endpoint).\n")
    lines.append("- On network-restricted machines, use healthy `.venv` fallback when `uv run --locked` handshake fails, then repair proxy/network before forced resync.\n")

    return "".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="Write docs/setup/TEST_ENV_INVENTORY.md")
    args = ap.parse_args()

    cmd_hits: DefaultDict[str, Set[str]] = defaultdict(set)
    env_hits: DefaultDict[str, Set[str]] = defaultdict(set)
    import_hits: DefaultDict[str, Set[str]] = defaultdict(set)

    for path in _iter_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        if path.suffix == ".py":
            _scan_python(path, text, cmd_hits, env_hits, import_hits)
        elif path.suffix == ".sh":
            _scan_shell(path, text, cmd_hits, env_hits)

    cmds = _normalize_cmds(cmd_hits)
    imports = _normalize_imports(import_hits)

    out = _render(cmds, env_hits, imports)

    if args.write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(out, encoding="utf-8")
        print(f"[test-env] wrote {OUT.relative_to(ROOT)}")
    else:
        sys.stdout.write(out)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
