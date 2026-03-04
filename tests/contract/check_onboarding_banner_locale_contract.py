#!/usr/bin/env python3
"""Contract: onboarding banner must support v2 visual layout + locale routing."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

BRANDING = ROOT / "docs" / "agents" / "BRANDING.md"
ONBOARDING = ROOT / "docs" / "agents" / "ONBOARDING.md"
SKILL = ROOT / ".agents" / "skills" / "leanatlas-onboard" / "SKILL.md"
EN_POLICY = ROOT / "tests" / "contract" / "check_english_only_policy.py"
ZH_BANNER = ROOT / "docs" / "agents" / "locales" / "zh-CN" / "ONBOARDING_BANNER.md"


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise SystemExit(f"[onboarding.banner][FAIL] {msg}")


def _read(path: Path) -> str:
    _require(path.exists(), f"missing required file: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def main() -> int:
    branding = _read(BRANDING)
    onboarding = _read(ONBOARDING)
    skill = _read(SKILL)
    en_policy = _read(EN_POLICY)

    _require("## Hero banner (v2)" in branding, "BRANDING.md missing v2 hero banner section")
    _require("## Onboarding info panel (v2)" in branding, "BRANDING.md missing v2 info panel section")
    _require("Powered by LeanAtlas" in branding, "BRANDING.md missing powered-by line in visual spec")
    _require(
        "A) Full maintainer initialization (INIT_FOR_CODEX.md) [Recommended]" in branding,
        "BRANDING.md must define option A as full maintainer initialization (recommended)",
    )
    _require(
        "B) Python-only setup (.venv + core contracts)" in branding,
        "BRANDING.md must define option B as python-only setup",
    )

    _require(str(ZH_BANNER.relative_to(ROOT)) in skill, "onboard skill missing zh-CN banner path")
    _require("locale-aware" in skill.lower(), "onboard skill missing locale-aware banner routing rule")

    _require(str(ZH_BANNER.relative_to(ROOT)) in onboarding, "ONBOARDING.md missing zh-CN banner asset reference")
    _require("locale-aware" in onboarding.lower(), "ONBOARDING.md missing locale-aware onboarding rule")
    _require(
        "**A)** “Full maintainer init”" in onboarding and "**[Recommended]**" in onboarding,
        "ONBOARDING.md must mark option A as full maintainer init (recommended)",
    )
    _require("**B)** “Python-only”" in onboarding, "ONBOARDING.md must define option B as python-only")
    _require(
        "**A) Full maintainer initialization (recommended)**" in skill,
        "onboard skill must mark option A as full maintainer initialization (recommended)",
    )
    _require("### A) Full maintainer init" in skill, "onboard skill missing execution section for option A")
    _require("### B) Python-only" in skill, "onboard skill missing execution section for option B")

    zh = _read(ZH_BANNER)
    _require("# LeanAtlas onboarding banner (zh-CN)" in zh, "zh-CN banner file missing title")
    _require("Powered by LeanAtlas" in zh, "zh-CN banner missing hero footer line")
    _require(
        "\u2022 A) Full maintainer initialization\uff08INIT_FOR_CODEX.md\uff09\u3010\u63a8\u8350\u3011" in zh,
        "zh-CN banner must define option A as recommended full maintainer initialization",
    )
    _require(
        "\u2022 B) Python-only setup\uff08.venv + core contracts\uff09" in zh,
        "zh-CN banner must define option B as python-only setup",
    )
    _require(
        "\u6b22\u8fce\u4f7f\u7528 LeanAtlas" in zh,
        "zh-CN banner missing Chinese welcome heading",
    )

    _require("ALLOWED_CJK_FILES" in en_policy, "english-only policy missing CJK allowlist variable")
    _require(
        str(ZH_BANNER.relative_to(ROOT)) in en_policy,
        "english-only policy must allowlist zh-CN onboarding banner file",
    )

    print("[onboarding.banner] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
