#!/usr/bin/env python3
"""Contract check: stale active 2026-03-06 LOOP execplans must be closed out."""

from __future__ import annotations

import sys
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

try:
    import yaml
    from yaml.nodes import MappingNode, ScalarNode
except Exception as exc:  # pragma: no cover - repo test env should provide PyYAML
    raise RuntimeError("check_execplan_closeout_hygiene.py requires PyYAML in the test environment") from exc


def _fail(msg: str) -> int:
    print(f"[execplan-closeout-hygiene][FAIL] {msg}", file=sys.stderr)
    return 2


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _front_matter_status(text: str) -> str | None:
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end < 0:
        return None
    header = text[4:end]
    try:
        node = yaml.compose(header)
        data = yaml.safe_load(header)
    except Exception:
        return None
    if not isinstance(node, MappingNode):
        return None
    status_keys = 0
    for key_node, _value_node in node.value:
        if not isinstance(key_node, ScalarNode):
            continue
        if key_node.value == "<<":
            continue
        if key_node.value == "status":
            status_keys += 1
    if status_keys != 1:
        return None
    if not isinstance(data, dict):
        return None
    value = data.get("status")
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _outcomes_section(text: str) -> str:
    heading = re.search(
        r"^## Outcomes & retrospective(?: \(fill when done\))?\s*$",
        text,
        flags=re.MULTILINE,
    )
    if heading is None:
        return ""
    body = text[heading.end() :].lstrip("\n")
    next_header = re.search(r"^##\s+", body, flags=re.MULTILINE)
    if next_header:
        body = body[: next_header.start()]
    return body.strip()


def main() -> int:
    targets = [
        ROOT / "docs" / "agents" / "execplans" / "20260306_maintainer_loop_visibility_wait_policy_v0.md",
        ROOT / "docs" / "agents" / "execplans" / "20260306_review_runner_semantic_idle_v0.md",
    ]
    for path in targets:
        text = _read(path)
        status = _front_matter_status(text)
        if status is None:
            return _fail(f"{path.name} must keep valid YAML front matter with an explicit status")
        if status == "active":
            return _fail(f"{path.name} must not remain status: active once the closeout is recorded")
        outcomes = _outcomes_section(text)
        if not outcomes:
            return _fail(f"{path.name} must keep a non-empty outcomes section after closeout")
        if re.search(r"(?m)^\s*-\s*Pending\.?\s*$", outcomes):
            return _fail(f"{path.name} must not keep the placeholder pending outcomes after closeout")
    print("[execplan-closeout-hygiene][PASS] stale 2026-03-06 LOOP execplans are closed out")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
