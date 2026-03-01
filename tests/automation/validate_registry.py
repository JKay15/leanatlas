#!/usr/bin/env python3
"""Validate automations/registry.json.

This is **spec-level TDD**: it should be fast, deterministic, and not require Codex.

Rules:
- Registry must parse as JSON.
- Each automation must include required structural keys.
- For status!=deprecated: must include tdd.profile + tdd.dry_run.cmd (spec-level).
- Referenced repo-local scripts must exist.
- Declared deterministic artifacts must stay in gitignored output roots.

This test is part of the *core* tier.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REG = ROOT / "automations" / "registry.json"


def die(msg: str) -> int:
  print(f"[automation.registry] ERROR: {msg}", file=sys.stderr)
  return 2


def require(cond: bool, msg: str) -> None:
  if not cond:
    raise AssertionError(msg)


def check_repo_local_script(cmd: list[str]) -> None:
  """Best-effort check: if command is python <path>, ensure path exists in repo."""
  if len(cmd) >= 2 and cmd[0] in {"python", "python3"}:
    p = ROOT / cmd[1]
    require(p.exists(), f"Missing script referenced by automation: {cmd[0]} {cmd[1]}")


def check_artifact_path(path: str, aid: str) -> None:
  allowed = ("artifacts/", ".cache/leanatlas/")
  require(
      any(path.startswith(prefix) for prefix in allowed),
      f"deterministic.artifacts path must be under artifacts/ or .cache/leanatlas/: {aid} -> {path}",
  )


def main() -> int:
  if not REG.exists():
    return die("automations/registry.json not found")

  data = json.loads(REG.read_text(encoding="utf-8"))
  require(data.get("version") == "1", "registry.version must be '1'")
  autos = data.get("automations")
  require(isinstance(autos, list) and autos, "registry.automations must be a non-empty list")

  seen: set[str] = set()
  for a in autos:
    require(isinstance(a, dict), "each automation must be an object")
    aid = a.get("id")
    require(isinstance(aid, str) and aid, "automation.id must be a non-empty string")
    require(aid not in seen, f"duplicate automation id: {aid}")
    seen.add(aid)

    status = a.get("status")
    require(status in {"active", "planned", "deprecated"}, f"automation.status invalid: {aid}")

    mode = a.get("mode")
    require(mode in {"OPERATOR", "MAINTAINER"}, f"automation.mode invalid: {aid}")

    trig = a.get("trigger")
    require(isinstance(trig, dict), f"automation.trigger must be object: {aid}")
    require(trig.get("type") in {"schedule", "event"}, f"automation.trigger.type invalid: {aid}")

    det = a.get("deterministic")
    require(isinstance(det, dict), f"automation.deterministic must be object: {aid}")
    steps = det.get("steps")
    require(isinstance(steps, list) and steps, f"automation.deterministic.steps must be non-empty list: {aid}")
    artifacts = det.get("artifacts")
    require(isinstance(artifacts, list) and artifacts, f"automation.deterministic.artifacts must be non-empty list: {aid}")
    for art in artifacts:
      require(isinstance(art, str) and art.strip(), f"deterministic.artifacts must contain non-empty strings: {aid}")
      check_artifact_path(str(art), aid)

    for s in steps:
      require(isinstance(s, dict), f"step must be object: {aid}")
      require(isinstance(s.get("name"), str) and s.get("name"), f"step.name required: {aid}")
      cmd = s.get("cmd")
      require(isinstance(cmd, list) and cmd and all(isinstance(x, str) for x in cmd), f"step.cmd must be string list: {aid}")
      check_repo_local_script(cmd)

    ver = a.get("verify")
    require(isinstance(ver, dict), f"automation.verify must be object: {aid}")
    vsteps = ver.get("steps")
    require(isinstance(vsteps, list) and vsteps, f"automation.verify.steps must be non-empty list: {aid}")
    for vs in vsteps:
      require(isinstance(vs, dict), f"verify step must be object: {aid}")
      cmd = vs.get("cmd")
      require(isinstance(cmd, list) and cmd and all(isinstance(x, str) for x in cmd), f"verify.step.cmd must be string list: {aid}")
      check_repo_local_script(cmd)

    if status != "deprecated":
      tdd = a.get("tdd")
      require(isinstance(tdd, dict), f"automation must have tdd: {aid}")
      profile = tdd.get("profile")
      require(profile in {"core", "nightly"}, f"tdd.profile invalid: {aid}")
      dry = tdd.get("dry_run")
      require(isinstance(dry, dict), f"tdd.dry_run must be object: {aid}")
      cmd = dry.get("cmd")
      require(isinstance(cmd, list) and cmd and all(isinstance(x, str) for x in cmd), f"tdd.dry_run.cmd must be string list: {aid}")
      check_repo_local_script(cmd)

    advisor = a.get("advisor")
    if isinstance(advisor, dict):
      enabled = bool(advisor.get("enabled"))
      if enabled:
        require(advisor.get("when") == "findings", f"advisor.when must be 'findings' when enabled: {aid}")

      probe = advisor.get("probe")
      if probe is not None:
        require(isinstance(probe, dict), f"advisor.probe must be an object when present: {aid}")
        kind = probe.get("kind")
        require(
            kind in {"json_array_nonempty", "json_field_truthy", "json_field_gt"},
            f"advisor.probe.kind invalid: {aid}",
        )
        path = probe.get("path")
        require(isinstance(path, str) and path.strip(), f"advisor.probe.path must be non-empty string: {aid}")
        check_artifact_path(str(path), aid)
        field = probe.get("field")
        require(isinstance(field, str) and field.strip(), f"advisor.probe.field must be non-empty string: {aid}")
        if kind == "json_field_gt":
          threshold = probe.get("threshold")
          require(isinstance(threshold, (int, float)), f"advisor.probe.threshold must be numeric: {aid}")

      exec_cmd = advisor.get("exec_cmd")
      if exec_cmd is not None:
        require(
            isinstance(exec_cmd, list) and exec_cmd and all(isinstance(x, str) for x in exec_cmd),
            f"advisor.exec_cmd must be a non-empty string list when present: {aid}",
        )
        check_repo_local_script(exec_cmd)

  print(f"[automation.registry] OK: {len(autos)} automations")
  return 0


if __name__ == "__main__":
  try:
    raise SystemExit(main())
  except AssertionError as e:
    print(f"[automation.registry] FAIL: {e}", file=sys.stderr)
    raise SystemExit(2)
