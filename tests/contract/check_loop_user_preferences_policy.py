#!/usr/bin/env python3
"""Contract: LOOP user preferences must be staged as post-onboarding presets."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _fail(msg: str) -> int:
    print(f"[loop-user-preferences][FAIL] {msg}", file=sys.stderr)
    return 2


def _read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise FileNotFoundError(rel)
    return path.read_text(encoding="utf-8")


def main() -> int:
    try:
        from tools.loop.user_preferences import (
            DEFAULT_ASSURANCE_PRESETS,
            DEFAULT_AGENT_PROVIDER_ID,
            DEFAULT_FAST_REVIEWER_PROFILES,
            DEFAULT_PREFERENCE_ARTIFACT_REL,
            build_preference_record,
            default_preference_artifact_path,
            load_preference_record,
            resolve_effective_preferences,
            write_preference_record,
        )
    except Exception as ex:  # noqa: BLE001
        return _fail(f"missing LOOP user-preference module surface: {ex}")

    if DEFAULT_ASSURANCE_PRESETS != ("Balanced", "Budget Saver", "Auditable"):
        return _fail("unexpected assurance preset list")
    if DEFAULT_FAST_REVIEWER_PROFILES != ("low", "medium"):
        return _fail("unexpected FAST reviewer profiles")
    if DEFAULT_AGENT_PROVIDER_ID != "codex_cli":
        return _fail("default provider should stay codex_cli")
    if DEFAULT_PREFERENCE_ARTIFACT_REL != ".cache/leanatlas/onboarding/loop_preferences.json":
        return _fail("unexpected LOOP preference artifact path")

    onboarding = _read("docs/agents/ONBOARDING.md")
    quickstart = _read("docs/setup/QUICKSTART.md")
    mainline = _read("docs/agents/LOOP_MAINLINE.md")
    onboard_skill = _read(".agents/skills/leanatlas-onboard/SKILL.md")
    mainline_skill = _read(".agents/skills/leanatlas-loop-mainline/SKILL.md")
    review_skill = _read(".agents/skills/leanatlas-loop-review-acceleration/SKILL.md")

    required_docs = {
        "docs/agents/ONBOARDING.md": [
            ".cache/leanatlas/onboarding/loop_preferences.json",
            "post-onboarding",
            "Balanced",
            "Budget Saver",
            "Auditable",
        ],
        "docs/setup/QUICKSTART.md": [
            ".cache/leanatlas/onboarding/loop_preferences.json",
            "Balanced",
            "Budget Saver",
            "Auditable",
        ],
        "docs/agents/LOOP_MAINLINE.md": [
            "User preference presets",
            "Balanced",
            "Budget Saver",
            "Auditable",
        ],
    }
    loaded = {
        "docs/agents/ONBOARDING.md": onboarding,
        "docs/setup/QUICKSTART.md": quickstart,
        "docs/agents/LOOP_MAINLINE.md": mainline,
    }
    for rel, snippets in required_docs.items():
        text = loaded[rel]
        for snippet in snippets:
            if snippet not in text:
                return _fail(f"{rel} missing required snippet `{snippet}`")

    if ".cache/leanatlas/onboarding/loop_preferences.json" not in onboard_skill:
        return _fail("onboarding skill must mention LOOP preference artifact")
    if "post-onboarding" not in onboard_skill.lower():
        return _fail("onboarding skill must treat LOOP defaults as post-onboarding")
    if "Balanced" not in mainline_skill or "Budget Saver" not in mainline_skill or "Auditable" not in mainline_skill:
        return _fail("mainline skill must route users through preset names")
    if "large-scope" not in review_skill or "pyramid" not in review_skill.lower():
        return _fail("review acceleration skill must explain large-scope pyramid preference")

    with tempfile.TemporaryDirectory(prefix="loop_user_prefs_") as td:
        repo_root = Path(td)
        artifact_path = default_preference_artifact_path(repo_root)
        if artifact_path != repo_root / ".cache" / "leanatlas" / "onboarding" / "loop_preferences.json":
            return _fail("artifact path helper returned unexpected location")

        record = build_preference_record(
            assurance_preset="Balanced",
            agent_provider_id="codex_cli",
            fast_reviewer_profile="low",
            allow_pyramid_review_for_large_scope=True,
        )
        write_preference_record(repo_root=repo_root, record=record)
        loaded_record = load_preference_record(repo_root=repo_root)
        if loaded_record["defaults"]["assurance_preset"] != "Balanced":
            return _fail("stored preference record lost assurance preset")

        resolved = resolve_effective_preferences(
            repo_root=repo_root,
            overrides={"assurance_preset": "Budget Saver", "fast_reviewer_profile": "medium"},
        )
        effective = resolved["effective_defaults"]
        if effective["assurance_preset"] != "Budget Saver":
            return _fail("override did not supersede stored assurance preset")
        if effective["fast_reviewer_profile"] != "medium":
            return _fail("override did not supersede stored reviewer profile")

        reloaded = json.loads(artifact_path.read_text(encoding="utf-8"))
        if reloaded["defaults"]["assurance_preset"] != "Balanced":
            return _fail("per-run overrides must not mutate the stored preference artifact")

        if resolved["effective_runtime"]["assurance_level"] != "FAST":
            return _fail("Budget Saver must map to FAST assurance_level")
        if not resolved["stored_defaults"]["allow_pyramid_review_for_large_scope"]:
            return _fail("stored preference should preserve the pyramid-review toggle")

    print("[loop-user-preferences] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
