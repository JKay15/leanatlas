#!/usr/bin/env python3
"""Deterministic skills/capabilities regen + audit (Phase5 platform).

This tool consumes *capability manifests* owned by Phase3/4/5 and produces:
- a merged, machine-readable "view" of the interface surface
- an audit report to prevent silent drift

Hard rule: **no business semantics**.
We only validate structural consistency and repo-local referential integrity.

Platform extensions (still non-semantic):
- Validate that repo skills follow the Agent Skills spec (YAML frontmatter).
- Validate that every capability command has at least one covering skill
  (an "empty manual" is still a manual).

Outputs (SKILLS_REGEN_CONTRACT v0):
- artifacts/skills_regen/view.json
- artifacts/skills_regen/audit.json

Determinism:
- No timestamps.
- Canonical JSON formatting.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import yaml


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def sha256_text(txt: str) -> str:
    h = hashlib.sha256()
    h.update(txt.encode("utf-8"))
    return h.hexdigest()


def load_doc_pack_id(repo_root: Path) -> Dict[str, Any]:
    p = repo_root / "DOC_PACK_ID.json"
    if not p.exists():
        return {}
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def is_placeholder(s: str) -> bool:
    s2 = s.lower()
    return ("placeholder" in s2) or ("todo" in s2) or ("tbd" in s2)


def extract_repo_local_python_script(entry: str) -> Optional[str]:
    """Best-effort parse: find the python script path inside a shell-ish command.

    Supported forms:
      - python tools/x.py ...
      - uv run --locked python tools/x.py ...
      - python3 tools/x.py ...

    Returns the repo-relative script path (string) if it looks like a .py file path.
    Returns None if not applicable (e.g., python -m module, lake exe, placeholder).
    """
    if is_placeholder(entry):
        return None

    try:
        toks = shlex.split(entry.replace("\n", " "))
    except Exception:
        # Unparseable commands are audited as warnings elsewhere.
        return None

    for i, t in enumerate(toks):
        if t in {"python", "python3"} and i + 1 < len(toks):
            nxt = toks[i + 1]
            # python -m module
            if nxt == "-m":
                return None
            # Heuristic: treat "foo/bar.py" or "bar.py" as a script path.
            if nxt.endswith(".py") and not nxt.startswith("-"):
                return nxt
    return None


@dataclass
class Audit:
    errors: List[str]
    warnings: List[str]

    def err(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)


SKILL_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def parse_skill_frontmatter(skill_md: Path) -> Tuple[Dict[str, Any], str]:
    """Parse YAML frontmatter + body.

    Agent Skills spec: SKILL.md must start with YAML frontmatter delimited by --- ... ---.
    """
    txt = skill_md.read_text(encoding="utf-8")
    lines = txt.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("SKILL.md must start with YAML frontmatter '---'")

    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        raise ValueError("SKILL.md frontmatter is missing closing '---'")

    fm_text = "\n".join(lines[1:end]).strip() + "\n"
    body = "\n".join(lines[end + 1 :]).lstrip("\n")

    fm = yaml.safe_load(fm_text) if fm_text.strip() else {}
    if not isinstance(fm, dict):
        raise ValueError("SKILL.md frontmatter must be a YAML mapping")
    return fm, body


def validate_skill_frontmatter(skill_dir: Path, fm: Dict[str, Any], audit: Audit) -> Tuple[str, str]:
    """Return (name, description) if valid; record audit errors otherwise."""
    name = fm.get("name")
    desc = fm.get("description")

    if not isinstance(name, str) or not name.strip():
        audit.err(f"skill missing name: {skill_dir.as_posix()}")
        name = ""
    else:
        name = name.strip()

    if not isinstance(desc, str) or not desc.strip():
        audit.err(f"skill missing description: {skill_dir.as_posix()}")
        desc = ""
    else:
        desc = desc.strip()

    # Agent Skills spec constraints.
    if name:
        if len(name) > 64:
            audit.err(f"skill.name too long (>64): {name} ({skill_dir.as_posix()})")
        if not SKILL_NAME_RE.fullmatch(name):
            audit.err(
                f"skill.name must match ^[a-z0-9]+(?:-[a-z0-9]+)*$: {name} ({skill_dir.as_posix()})"
            )

        # Must match directory name
        if name != skill_dir.name:
            audit.err(
                f"skill.name must match parent directory name: name={name} dir={skill_dir.name} ({skill_dir.as_posix()})"
            )

    if desc:
        if len(desc) > 1024:
            audit.err(f"skill.description too long (>1024): {name} ({skill_dir.as_posix()})")

    return name, desc


def load_skill_coverage(skill_dir: Path, audit: Audit) -> List[str]:
    cov = skill_dir / "references" / "coverage.yaml"
    if not cov.exists():
        return []
    try:
        data = yaml.safe_load(cov.read_text(encoding="utf-8"))
    except Exception as e:
        audit.err(f"failed to parse coverage.yaml: {cov.as_posix()}: {e}")
        return []
    if not isinstance(data, dict):
        audit.err(f"coverage.yaml must be a mapping: {cov.as_posix()}")
        return []

    cmds = data.get("covers_commands")
    if cmds is None:
        return []
    if not isinstance(cmds, list) or not all(isinstance(x, str) and x.strip() for x in cmds):
        audit.err(f"coverage.yaml covers_commands must be a non-empty string list (or omitted): {cov.as_posix()}")
        return []

    # Deterministic ordering + de-dup.
    out = sorted(set([x.strip() for x in cmds]))
    return out


def discover_skill_dirs(repo_root: Path) -> List[Path]:
    """Discover repo-scoped skills.

    Codex scans .agents/skills from CWD up to repo root; for this repo we validate
    the repo-root skill inventory: <repo_root>/.agents/skills/*/SKILL.md.
    """
    base = repo_root / ".agents" / "skills"
    if not base.exists() or not base.is_dir():
        return []
    out: List[Path] = []
    for child in sorted([p for p in base.iterdir() if p.is_dir()], key=lambda p: p.name):
        if (child / "SKILL.md").exists():
            out.append(child)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".")
    ap.add_argument(
        "--out",
        default="artifacts/skills_regen/view.json",
        help="Output view JSON (deterministic)",
    )
    ap.add_argument(
        "--audit-out",
        default="artifacts/skills_regen/audit.json",
        help="Output audit JSON (deterministic)",
    )
    ap.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if audit has any errors",
    )
    args = ap.parse_args()

    repo_root = Path(args.repo_root).resolve()

    doc_pack = load_doc_pack_id(repo_root)
    doc_pack_version = doc_pack.get("doc_pack_version")
    content_hash = doc_pack.get("content_hash_sha256")

    manifest_paths = [
        repo_root / "tools" / "capabilities" / "phase3.yaml",
        repo_root / "tools" / "capabilities" / "phase4.yaml",
        repo_root / "tools" / "capabilities" / "phase5.yaml",
    ]

    manifests: Dict[str, Dict[str, Any]] = {}
    audit = Audit(errors=[], warnings=[])

    for p in manifest_paths:
        if not p.exists():
            audit.err(f"missing manifest: {p.relative_to(repo_root).as_posix()}")
            continue
        txt = p.read_text(encoding="utf-8")
        try:
            data = yaml.safe_load(txt)
        except Exception as e:
            audit.err(f"failed to parse yaml: {p.relative_to(repo_root).as_posix()}: {e}")
            continue
        if not isinstance(data, dict):
            audit.err(f"manifest is not a mapping: {p.relative_to(repo_root).as_posix()}")
            continue
        phase = data.get("phase")
        if not isinstance(phase, str) or not phase:
            audit.err(f"manifest missing 'phase': {p.relative_to(repo_root).as_posix()}")
            continue
        manifests[phase] = data

        # Placeholder detection at file level.
        if "placeholder" in txt.lower():
            audit.warn(f"manifest contains placeholder markers: {p.relative_to(repo_root).as_posix()}")

    # Merge commands into a stable view.
    merged_commands: List[Dict[str, Any]] = []
    seen_ids: Dict[str, str] = {}

    for phase in sorted(manifests.keys()):
        data = manifests[phase]
        cmds = data.get("commands") or []
        if not isinstance(cmds, list):
            audit.err(f"{phase}: commands is not a list")
            continue

        for c in cmds:
            if not isinstance(c, dict):
                audit.err(f"{phase}: command entry is not an object")
                continue
            cid = c.get("id")
            if not isinstance(cid, str) or not cid:
                audit.err(f"{phase}: command missing id")
                continue

            if cid in seen_ids:
                audit.err(f"duplicate command id across phases: {cid} ({seen_ids[cid]} vs {phase})")
            else:
                seen_ids[cid] = phase

            entry = c.get("entrypoint")
            if isinstance(entry, str):
                if is_placeholder(entry):
                    audit.warn(f"{phase}.{cid}: placeholder entrypoint")
                else:
                    script = extract_repo_local_python_script(entry)
                    if script is not None:
                        sp = repo_root / script
                        if not sp.exists():
                            audit.err(f"{phase}.{cid}: missing repo-local script referenced by entrypoint: {script}")

            # Smoke commands should also avoid bitrot.
            smoke = c.get("smoke") or []
            if isinstance(smoke, list):
                for s in smoke:
                    if not isinstance(s, str):
                        continue
                    if is_placeholder(s):
                        audit.warn(f"{phase}.{cid}: placeholder smoke")
                        continue
                    script = extract_repo_local_python_script(s)
                    if script is not None:
                        sp = repo_root / script
                        if not sp.exists():
                            audit.err(f"{phase}.{cid}: missing repo-local script referenced by smoke: {script}")

            merged_commands.append(
                {
                    "phase": phase,
                    "id": cid,
                    "entrypoint": c.get("entrypoint"),
                    "description": c.get("description"),
                    "inputs": c.get("inputs"),
                    "outputs": c.get("outputs"),
                    "schemas": c.get("schemas") or [],
                    "deps": c.get("deps") or [],
                    "smoke": c.get("smoke") or [],
                }
            )

    merged_commands = sorted(merged_commands, key=lambda x: (str(x.get("phase")), str(x.get("id"))))
    command_ids: Set[str] = set([str(c.get("id")) for c in merged_commands if isinstance(c.get("id"), str)])

    # Manifest hashes (stable provenance)
    manifest_info: List[Dict[str, Any]] = []
    for p in manifest_paths:
        rel = p.relative_to(repo_root).as_posix()
        if not p.exists():
            continue
        txt = p.read_text(encoding="utf-8")
        manifest_info.append({"path": rel, "sha256": sha256_text(txt)})
    manifest_info = sorted(manifest_info, key=lambda x: str(x["path"]))

    # Skills inventory + coverage
    skills: List[Dict[str, Any]] = []
    skill_name_to_path: Dict[str, str] = {}
    command_coverage: Dict[str, List[str]] = {cid: [] for cid in sorted(command_ids)}

    for sdir in discover_skill_dirs(repo_root):
        smd = sdir / "SKILL.md"
        rel_dir = sdir.relative_to(repo_root).as_posix()

        try:
            fm, _body = parse_skill_frontmatter(smd)
        except Exception as e:
            audit.err(f"invalid skill frontmatter: {rel_dir}/SKILL.md: {e}")
            continue

        name, desc = validate_skill_frontmatter(sdir, fm, audit)
        if not name:
            # If name invalid, don't attempt coverage mapping.
            continue

        if name in skill_name_to_path:
            audit.err(f"duplicate skill name: {name} ({skill_name_to_path[name]} vs {rel_dir})")
        else:
            skill_name_to_path[name] = rel_dir

        covers = load_skill_coverage(sdir, audit)
        # Validate: coverage references known commands.
        for cid in covers:
            if cid not in command_ids:
                audit.warn(f"skill {name} covers unknown command id: {cid}")

        # Register coverage for known commands.
        for cid in covers:
            if cid in command_coverage:
                command_coverage[cid].append(name)

        skills.append(
            {
                "name": name,
                "description": desc,
                "path": rel_dir,
                "covers_commands": sorted([c for c in covers if c in command_ids]),
            }
        )

    # Deterministic ordering + de-dup lists.
    skills = sorted(skills, key=lambda x: str(x.get("name")))
    for cid in list(command_coverage.keys()):
        command_coverage[cid] = sorted(set(command_coverage[cid]))

    # Coverage requirement: every command must be covered by >= 1 skill.
    uncovered = [cid for cid, sks in command_coverage.items() if not sks]
    for cid in uncovered:
        # Mention phase for easier routing.
        ph = seen_ids.get(cid, "?")
        audit.err(f"uncovered command (no skill manual): {cid} (phase={ph})")

    view = {
        "schema": "leanatlas.skills_regen.view",
        "schema_version": "0.2.0",
        "doc_pack_version": doc_pack_version,
        "content_hash_sha256": content_hash,
        "manifests": manifest_info,
        "commands": merged_commands,
        "skills": skills,
        "command_coverage": command_coverage,
    }

    audit_obj = {
        "schema": "leanatlas.skills_regen.audit",
        "schema_version": "0.2.0",
        "doc_pack_version": doc_pack_version,
        "content_hash_sha256": content_hash,
        "counts": {
            "phases": len(manifests),
            "commands": len(merged_commands),
            "skills": len(skills),
            "uncovered_commands": len(uncovered),
            "errors": len(audit.errors),
            "warnings": len(audit.warnings),
        },
        "errors": sorted(audit.errors),
        "warnings": sorted(audit.warnings),
    }

    out_path = (repo_root / args.out).resolve() if not Path(args.out).is_absolute() else Path(args.out)
    audit_path = (
        (repo_root / args.audit_out).resolve() if not Path(args.audit_out).is_absolute() else Path(args.audit_out)
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.parent.mkdir(parents=True, exist_ok=True)

    out_path.write_text(canonical_json(view), encoding="utf-8")
    audit_path.write_text(canonical_json(audit_obj), encoding="utf-8")

    # User-friendly stdout for humans/Codex.
    rel_out = out_path
    rel_audit = audit_path
    try:
        rel_out = out_path.relative_to(repo_root)
        rel_audit = audit_path.relative_to(repo_root)
    except Exception:
        pass

    print(f"[skills_regen] wrote {rel_out}")
    print(f"[skills_regen] wrote {rel_audit}")

    if args.check and audit.errors:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
