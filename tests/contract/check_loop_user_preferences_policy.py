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
            DEFAULT_ASSURANCE_PRESET,
            DEFAULT_ASSURANCE_PRESETS,
            DEFAULT_AGENT_PROVIDER_ID,
            DEFAULT_FAST_REVIEWER_PROFILES,
            DEFAULT_FAST_REVIEWER_PROFILE,
            DEFAULT_MEDIUM_ESCALATION_POLICY,
            DEFAULT_PREFERENCE_ARTIFACT_REL,
            DEFAULT_REVIEW_TIER_POLICIES,
            DEFAULT_REVIEW_TIER_POLICY,
            DEFAULT_STRICT_EXCEPTION_POLICY,
            build_default_review_policy,
            build_preference_record,
            default_preference_artifact_path,
            load_preference_record,
            resolve_effective_preferences,
            write_preference_record,
        )
    except Exception as ex:  # noqa: BLE001
        return _fail(f"missing LOOP user-preference module surface: {ex}")

    if DEFAULT_ASSURANCE_PRESETS != ("Budget Saver", "Balanced", "Auditable"):
        return _fail("unexpected assurance preset list")
    if DEFAULT_ASSURANCE_PRESET != "Budget Saver":
        return _fail("default assurance preset must be Budget Saver")
    if DEFAULT_FAST_REVIEWER_PROFILES != ("low", "medium"):
        return _fail("unexpected FAST reviewer profiles")
    if DEFAULT_FAST_REVIEWER_PROFILE != "low":
        return _fail("default FAST reviewer profile must be low")
    if DEFAULT_REVIEW_TIER_POLICIES != ("LOW_ONLY", "LOW_PLUS_MEDIUM"):
        return _fail("unexpected review tier policy enum")
    if DEFAULT_REVIEW_TIER_POLICY != "LOW_PLUS_MEDIUM":
        return _fail("default review tier policy must be LOW_PLUS_MEDIUM")
    if DEFAULT_AGENT_PROVIDER_ID != "codex_cli":
        return _fail("default provider should stay codex_cli")
    if DEFAULT_PREFERENCE_ARTIFACT_REL != ".cache/leanatlas/onboarding/loop_preferences.json":
        return _fail("unexpected LOOP preference artifact path")
    if DEFAULT_MEDIUM_ESCALATION_POLICY != "SMALL_SCOPE_HIGH_RISK_CORE_LOGIC_ONLY":
        return _fail("unexpected medium escalation policy")
    if DEFAULT_STRICT_EXCEPTION_POLICY != "EXPLICIT_EXCEPTION_ONLY":
        return _fail("unexpected strict exception policy")

    default_policy = build_default_review_policy()
    if default_policy["assurance_preset"] != "Budget Saver":
        return _fail("default review policy must recommend Budget Saver")
    if default_policy["assurance_level"] != "FAST":
        return _fail("default review policy must recommend FAST assurance")
    if default_policy["fast_reviewer_profile"] != "low":
        return _fail("default review policy must recommend low FAST reviewer profile")
    if default_policy["review_tier_policy"] != "LOW_PLUS_MEDIUM":
        return _fail("default review policy must expose LOW_PLUS_MEDIUM as the committed tier policy")
    if default_policy["medium_escalation_profile"] != "medium":
        return _fail("default review policy must expose medium as the bounded escalation profile")

    onboarding = _read("docs/agents/ONBOARDING.md")
    quickstart = _read("docs/setup/QUICKSTART.md")
    mainline = _read("docs/agents/LOOP_MAINLINE.md")
    onboard_skill = _read(".agents/skills/leanatlas-onboard/SKILL.md")
    mainline_skill = _read(".agents/skills/leanatlas-loop-mainline/SKILL.md")
    review_skill = _read(".agents/skills/leanatlas-loop-review-acceleration/SKILL.md")
    user_prefs_execplan = _read("docs/agents/execplans/20260308_loop_user_preferences_and_onboarding_defaults_v0.md")

    required_docs = {
        "docs/agents/ONBOARDING.md": [
            ".cache/leanatlas/onboarding/loop_preferences.json",
            "post-onboarding",
            "Budget Saver",
            "FAST + low",
            "LOW_PLUS_MEDIUM",
            "default reviewer tier policy",
            "small-scope high-risk core logic",
            "STRICT / xhigh",
            "exception",
            "Balanced",
            "Auditable",
        ],
        "docs/setup/QUICKSTART.md": [
            ".cache/leanatlas/onboarding/loop_preferences.json",
            "Budget Saver",
            "FAST + low",
            "LOW_PLUS_MEDIUM",
            "medium",
            "STRICT / xhigh",
            "Balanced",
            "Auditable",
        ],
        "docs/agents/LOOP_MAINLINE.md": [
            "User preference presets",
            "Budget Saver",
            "FAST + low",
            "LOW_PLUS_MEDIUM",
            "default reviewer tier policy",
            "small-scope high-risk core logic",
            "STRICT / xhigh",
            "Balanced",
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
    if "FAST + low" not in onboard_skill:
        return _fail("onboarding skill must identify FAST + low as the default reviewer path")
    if "LOW_PLUS_MEDIUM" not in onboard_skill:
        return _fail("onboarding skill must name the committed default reviewer tier policy")
    if "STRICT / xhigh" not in onboard_skill:
        return _fail("onboarding skill must mark STRICT / xhigh as exceptional")
    if "Budget Saver" not in mainline_skill or "FAST + low" not in mainline_skill:
        return _fail("mainline skill must route users through the FAST + low baseline")
    if "LOW_PLUS_MEDIUM" not in mainline_skill:
        return _fail("mainline skill must name the committed default reviewer tier policy")
    if "STRICT / xhigh" not in mainline_skill:
        return _fail("mainline skill must mark STRICT / xhigh as exceptional")
    if "Balanced" not in mainline_skill or "Auditable" not in mainline_skill:
        return _fail("mainline skill must route users through preset names")
    if "large-scope" not in review_skill or "pyramid" not in review_skill.lower():
        return _fail("review acceleration skill must explain large-scope pyramid preference")
    if "FAST + low" not in review_skill:
        return _fail("review acceleration skill must state the default FAST + low reviewer baseline")
    if "LOW_PLUS_MEDIUM" not in review_skill:
        return _fail("review acceleration skill must expose the committed default reviewer tier policy")
    if "medium" not in review_skill or "small-scope high-risk core logic" not in review_skill:
        return _fail("review acceleration skill must bound medium escalation to small high-risk scopes")
    if "STRICT / xhigh" not in review_skill:
        return _fail("review acceleration skill must mark STRICT / xhigh as exceptional")
    if "`Budget Saver` (recommended)" not in user_prefs_execplan:
        return _fail("user preferences execplan must mark Budget Saver as the recommended preset")
    if "`Balanced` maps to the recommended default development path" in user_prefs_execplan:
        return _fail("user preferences execplan must not still describe Balanced as the recommended default path")

    with tempfile.TemporaryDirectory(prefix="loop_user_prefs_") as td:
        repo_root = Path(td)
        artifact_path = default_preference_artifact_path(repo_root)
        if artifact_path != repo_root / ".cache" / "leanatlas" / "onboarding" / "loop_preferences.json":
            return _fail("artifact path helper returned unexpected location")

        record = build_preference_record()
        write_preference_record(repo_root=repo_root, record=record)
        loaded_record = load_preference_record(repo_root=repo_root)
        if loaded_record["defaults"]["assurance_preset"] != "Budget Saver":
            return _fail("stored preference record must default to Budget Saver")
        if loaded_record["defaults"]["fast_reviewer_profile"] != "low":
            return _fail("stored preference record must default to low FAST reviewer profile")
        if loaded_record["defaults"]["review_tier_policy"] != "LOW_PLUS_MEDIUM":
            return _fail("stored preference record must default to LOW_PLUS_MEDIUM tier policy")

        resolved = resolve_effective_preferences(
            repo_root=repo_root,
            overrides={"assurance_preset": "Balanced", "fast_reviewer_profile": "medium"},
        )
        effective = resolved["effective_defaults"]
        if effective["assurance_preset"] != "Balanced":
            return _fail("override did not supersede stored assurance preset")
        if effective["fast_reviewer_profile"] != "medium":
            return _fail("override did not supersede stored reviewer profile")
        if effective["review_tier_policy"] != "LOW_PLUS_MEDIUM":
            return _fail("review tier policy should remain LOW_PLUS_MEDIUM unless explicitly overridden")

        reloaded = json.loads(artifact_path.read_text(encoding="utf-8"))
        if reloaded["defaults"]["assurance_preset"] != "Budget Saver":
            return _fail("per-run overrides must not mutate the stored preference artifact")
        if reloaded["defaults"]["review_tier_policy"] != "LOW_PLUS_MEDIUM":
            return _fail("per-run overrides must not mutate the stored tier policy")

        if resolved["effective_runtime"]["assurance_level"] != "LIGHT":
            return _fail("Balanced override must map to LIGHT assurance_level")
        if resolved["effective_runtime"]["review_tier_policy"] != "LOW_PLUS_MEDIUM":
            return _fail("effective runtime must expose the committed LOW_PLUS_MEDIUM tier policy")
        if not resolved["stored_defaults"]["allow_pyramid_review_for_large_scope"]:
            return _fail("stored preference should preserve the pyramid-review toggle")

    print("[loop-user-preferences] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
