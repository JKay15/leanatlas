#!/usr/bin/env python3
"""Contract: publication/rematerialization runtime must be explicit and append-only."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _fail(msg: str) -> int:
    print(f"[loop-publication-runtime][FAIL] {msg}", file=sys.stderr)
    return 2


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    try:
        from tools.loop.publication import (
            publish_capability_event,
            publish_supervisor_guidance_event,
            record_human_external_input,
            rematerialize_context_pack,
        )
    except Exception as exc:  # noqa: BLE001
        return _fail(f"missing publication runtime surface: {exc}")

    with tempfile.TemporaryDirectory(prefix="loop_publication_runtime_") as td:
        repo = Path(td)
        contract = repo / "docs" / "contracts" / "LOOP_WAVE_EXECUTION_CONTRACT.md"
        execplan = repo / "docs" / "agents" / "execplans" / "active_plan.md"
        external_note = repo / ".cache" / "leanatlas" / "tmp" / "external" / "note.txt"
        capability_doc = repo / "docs" / "setup" / "LOOP_LIBRARY_QUICKSTART.md"
        _write(contract, "# contract\n")
        _write(execplan, "# plan\n")
        _write(external_note, "user supplied note\n")
        _write(capability_doc, "# quickstart\n")

        publication = publish_capability_event(
            repo_root=repo,
            publication_id="loop.default_review_execution",
            producer_id="batch_supervisor",
            summary="Default staged review execution is available.",
            resource_refs=[
                "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md",
                "docs/setup/LOOP_LIBRARY_QUICKSTART.md",
            ],
            capability_kind="CAPABILITY",
        )
        if publication["event_kind"] != "CAPABILITY":
            return _fail("capability publication must preserve event_kind=CAPABILITY")
        publication_ref = Path(str(publication["event_ref"]))
        if not publication_ref.exists():
            return _fail("capability publication must persist an immutable event artifact")
        publication_obj = _read_json(publication_ref)
        if publication_obj.get("resource_refs") != [
            "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md",
            "docs/setup/LOOP_LIBRARY_QUICKSTART.md",
        ]:
            return _fail("capability publication must preserve normalized resource refs")

        publication_again = publish_capability_event(
            repo_root=repo,
            publication_id="loop.default_review_execution",
            producer_id="batch_supervisor",
            summary="Default staged review execution is available.",
            resource_refs=[
                "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md",
                "docs/setup/LOOP_LIBRARY_QUICKSTART.md",
            ],
            capability_kind="CAPABILITY",
        )
        if publication_again["event_ref"] != publication["event_ref"]:
            return _fail("identical publication input should reuse the same immutable event ref")
        publication_journal = _read_jsonl(Path(str(publication["journal_ref"])))
        if len(publication_journal) != 1:
            return _fail("identical publication input must not append duplicate journal rows")

        ingress = record_human_external_input(
            repo_root=repo,
            ingress_id="human.note.001",
            producer_id="user",
            source_label="user_note",
            summary="Bounded user clarification for downstream wave.",
            evidence_refs=[external_note.relative_to(repo).as_posix()],
            related_context_refs=[execplan.relative_to(repo).as_posix()],
        )
        if ingress["event_kind"] != "HUMAN_EXTERNAL_INPUT":
            return _fail("human ingress must preserve HUMAN_EXTERNAL_INPUT event kind")
        ingress_ref = Path(str(ingress["event_ref"]))
        if not ingress_ref.exists():
            return _fail("human ingress must persist an explicit event artifact")
        ingress_obj = _read_json(ingress_ref)
        if ingress_obj.get("evidence_refs") != [external_note.relative_to(repo).as_posix()]:
            return _fail("human ingress must preserve explicit evidence refs")

        guidance = publish_supervisor_guidance_event(
            repo_root=repo,
            guidance_id="child.wave.guidance",
            producer_id="parent_supervisor",
            summary="Known conclusions and non-goals for the bounded xhigh child.",
            reminder_message="Do not restart broad discovery; move to bounded tests and patch work.",
            known_conclusion_refs=[execplan.relative_to(repo).as_posix()],
            non_goal_refs=[contract.relative_to(repo).as_posix()],
        )
        if guidance["event_kind"] != "SUPERVISOR_GUIDANCE":
            return _fail("supervisor guidance publication must preserve SUPERVISOR_GUIDANCE event kind")
        guidance_ref = Path(str(guidance["event_ref"]))
        if not guidance_ref.exists():
            return _fail("supervisor guidance publication must persist an explicit event artifact")
        guidance_obj = _read_json(guidance_ref)
        if guidance_obj.get("known_conclusion_refs") != [execplan.relative_to(repo).as_posix()]:
            return _fail("supervisor guidance must preserve explicit known_conclusion_refs")
        if guidance_obj.get("non_goal_refs") != [contract.relative_to(repo).as_posix()]:
            return _fail("supervisor guidance must preserve explicit non_goal_refs")
        if (
            guidance_obj.get("reminder_message")
            != "Do not restart broad discovery; move to bounded tests and patch work."
        ):
            return _fail("supervisor guidance must preserve the reminder message verbatim")

        context_pack = rematerialize_context_pack(
            repo_root=repo,
            context_id="child.wave.context",
            consumer_id="child_wave_002",
            base_context_refs=[execplan.relative_to(repo).as_posix()],
            publication_event_refs=[str(publication_ref)],
            human_ingress_event_refs=[str(ingress_ref)],
            supervisor_guidance_event_refs=[str(guidance_ref)],
        )
        context_ref = Path(str(context_pack["context_pack_ref"]))
        if not context_ref.exists():
            return _fail("rematerialization must persist a context-pack artifact")
        context_obj = _read_json(context_ref)
        publication_rel = publication_ref.resolve().relative_to(repo.resolve()).as_posix()
        ingress_rel = ingress_ref.resolve().relative_to(repo.resolve()).as_posix()
        guidance_rel = guidance_ref.resolve().relative_to(repo.resolve()).as_posix()
        if context_obj.get("publication_event_refs") != [publication_rel]:
            return _fail("context pack must canonicalize publication refs to repo-relative form")
        if context_obj.get("human_ingress_event_refs") != [ingress_rel]:
            return _fail("context pack must canonicalize human-ingress refs to repo-relative form")
        if context_obj.get("supervisor_guidance_event_refs") != [guidance_rel]:
            return _fail("context pack must canonicalize supervisor-guidance refs to repo-relative form")
        expected_required = [
            execplan.relative_to(repo).as_posix(),
            ingress_rel,
            publication_rel,
            guidance_rel,
        ]
        if context_obj.get("required_context_refs") != expected_required:
            return _fail("context pack must expose deterministic required_context_refs for downstream adoption")

        context_pack_again = rematerialize_context_pack(
            repo_root=repo,
            context_id="child.wave.context",
            consumer_id="child_wave_002",
            base_context_refs=[execplan.relative_to(repo).as_posix()],
            publication_event_refs=[str(publication_ref)],
            human_ingress_event_refs=[str(ingress_ref)],
            supervisor_guidance_event_refs=[str(guidance_ref)],
        )
        if context_pack_again["context_pack_ref"] != context_pack["context_pack_ref"]:
            return _fail("identical rematerialization input should reuse the same context-pack artifact")

        mixed_context_pack = rematerialize_context_pack(
            repo_root=repo,
            context_id="child.wave.context",
            consumer_id="child_wave_002",
            base_context_refs=[execplan.relative_to(repo).as_posix()],
            publication_event_refs=[
                str(publication_ref),
                publication_rel,
            ],
            human_ingress_event_refs=[
                ingress_rel,
                str(ingress_ref),
            ],
            supervisor_guidance_event_refs=[
                str(guidance_ref),
                guidance_rel,
            ],
        )
        if mixed_context_pack["context_pack_ref"] != context_pack["context_pack_ref"]:
            return _fail("absolute-vs-relative repo ref spelling must not fork deterministic context-pack identity")

        print("[loop-publication-runtime] OK")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
