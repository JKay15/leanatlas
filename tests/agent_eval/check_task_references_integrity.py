"""Agent-eval hardening: references must be curated + resolvable.

We want mentor-keyword tasks to be:
- traceable (sources exist)
- stable (no random URL rot scattered through task files)

Contract enforced here:
- Every `tests/agent_eval/tasks/mk_*/task.yaml` must have `references`.
- Each reference must be of the form `REF:<id>`.
- `<id>` must exist in `docs/references/mentor_keywords.yaml`.
- Each task must cite at least 2 refs.
- Fixture `Sources.md` files must cite only known IDs.
"""

from __future__ import annotations

from pathlib import Path
import re
import yaml

ROOT = Path(__file__).resolve().parents[2]

REFS_FILE = ROOT / "docs" / "references" / "mentor_keywords.yaml"
TASKS_DIR = ROOT / "tests" / "agent_eval" / "tasks"
FIXTURES_DIR = ROOT / "tests" / "agent_eval" / "fixtures" / "problems"


def load_ref_ids() -> set[str]:
    data = yaml.safe_load(REFS_FILE.read_text(encoding="utf-8"))
    entries = data.get("entries", [])
    ids = {e["id"] for e in entries}
    assert ids, "No reference IDs loaded"
    return ids


def iter_task_files() -> list[Path]:
    return sorted(TASKS_DIR.glob("mk_*/task.yaml"))


def iter_sources_md() -> list[Path]:
    return sorted(FIXTURES_DIR.glob("mk_*/Sources.md"))


def main() -> None:
    assert REFS_FILE.exists(), f"Missing references collection: {REFS_FILE}"

    known = load_ref_ids()

    # --- Task.yaml checks ---
    tasks = iter_task_files()
    assert tasks, "No mentor keyword tasks found"

    for p in tasks:
        task = yaml.safe_load(p.read_text(encoding="utf-8"))
        refs = task.get("references")
        assert isinstance(refs, list) and refs, f"{p}: references must be a non-empty list"
        assert len(refs) >= 2, f"{p}: must cite at least 2 references"

        for r in refs:
            assert isinstance(r, str), f"{p}: reference must be a string: {r!r}"
            assert not re.search(r"https?://", r), (
                f"{p}: task.yaml references must be REF:IDs only; move URLs into {REFS_FILE}.\n"
                f"Got: {r}"
            )
            assert r.startswith("REF:"), f"{p}: reference must start with REF:, got: {r}"
            ref_id = r.split("REF:", 1)[1].strip()
            assert ref_id in known, f"{p}: unknown ref id {ref_id!r} (not in {REFS_FILE})"

    # --- Fixture Sources.md checks ---
    sources_files = iter_sources_md()
    assert sources_files, "No fixture Sources.md files found"

    # IDs are written as backticked tokens: `ID`.
    token_re = re.compile(r"`([A-Z0-9_]+)`")

    for p in sources_files:
        txt = p.read_text(encoding="utf-8")
        ids = set(token_re.findall(txt))
        assert ids, f"{p}: expected at least one reference ID backticked in Sources.md"
        unknown = sorted(i for i in ids if i not in known)
        assert not unknown, f"{p}: unknown reference IDs in Sources.md: {unknown}"

    print("OK: task references and fixture Sources.md are consistent with mentor_keywords.yaml")


if __name__ == "__main__":
    main()
