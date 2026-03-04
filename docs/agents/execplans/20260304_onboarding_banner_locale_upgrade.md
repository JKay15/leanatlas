---
title: Upgrade onboarding banner to a richer terminal card with controlled zh-CN locale support
owner: Codex (MAINTAINER)
status: done
created: 2026-03-04
---

## Purpose / Big Picture
LeanAtlas onboarding currently uses a minimal geometric banner and does not provide a high-density card-style first impression comparable to polished terminal products. The user requested a more visual onboarding screen and explicitly requested non-English onboarding copy support. At the same time, the repository enforces an English-only policy through a core contract test. This plan upgrades onboarding visuals to a richer hero + info-card format and introduces a tightly scoped locale exception for a dedicated zh-CN onboarding banner asset. The result should preserve deterministic policy gates while enabling better UX and language-aware first-run messaging.

## Glossary
- Hero banner: top visual branding block rendered with monospaced box-drawing layout.
- Info panel: onboarding instruction card below the hero banner.
- Locale asset: language-specific content file for onboarding visual text.
- Controlled exception: explicit allowlist in policy checks for a narrow path.

## Scope
In scope:
- onboarding branding docs and onboarding skill banner instructions
- one dedicated zh-CN onboarding locale asset file
- English-only policy contract adjustment for a narrow allowlist
- new contract test for onboarding visual/locale routing requirements
- manifest/test-matrix/file-index regeneration

Out of scope:
- changing onboarding bootstrap command semantics
- changing automation readiness gate behavior
- introducing app-side modal UI features

## Interfaces and Files
- `docs/agents/BRANDING.md`
- `.agents/skills/leanatlas-onboard/SKILL.md`
- `docs/agents/ONBOARDING.md`
- `docs/agents/archive/AGENTS_ONBOARDING_VERBOSE.md`
- `docs/agents/CODEX_APP_PROMPTS.md`
- `docs/agents/locales/zh-CN/ONBOARDING_BANNER.md` (new)
- `tests/contract/check_english_only_policy.py`
- `tests/contract/check_onboarding_banner_locale_contract.py` (new)
- `tests/manifest.json`
- regenerated:
  - `docs/navigation/FILE_INDEX.md`
  - `docs/testing/TEST_MATRIX.md`

## Milestones
1) TDD: add onboarding banner/locale contract
- Deliverables:
  - `tests/contract/check_onboarding_banner_locale_contract.py`
  - `tests/manifest.json` entry
- Commands:
  - `./.venv/bin/python tests/contract/check_onboarding_banner_locale_contract.py`
- Acceptance:
  - Fails before implementation due missing locale file/new required markers.

2) Implement visual/locale upgrade + policy exception
- Deliverables:
  - updated branding/skill/onboarding docs
  - new zh-CN locale asset
  - updated english-only policy check with narrow allowlist
- Commands:
  - `./.venv/bin/python tests/contract/check_onboarding_banner_locale_contract.py`
  - `./.venv/bin/python tests/contract/check_english_only_policy.py`
- Acceptance:
  - New contract passes.
  - English-only policy still passes with only the allowlisted locale file containing CJK.

3) Regenerate generated docs and run full verification
- Deliverables:
  - regenerated file index + test matrix
  - plan status set to done
- Commands:
  - `./.venv/bin/python tools/docs/generate_file_index.py --write`
  - `./.venv/bin/python tools/tests/generate_test_matrix.py --write`
  - `./.venv/bin/python tests/run.py --profile core`
  - `./.venv/bin/python tests/run.py --profile nightly`
  - `lake build`
- Acceptance:
  - core/nightly/build pass (env-gated skips allowed).
  - no policy regression.

## Testing plan (TDD)
- Add `check_onboarding_banner_locale_contract.py` to assert:
  - branding defines a richer hero banner section and info panel section
  - onboarding skill references locale-aware banner selection and the zh-CN file path
  - zh-CN locale asset exists and includes required structured blocks
- Register this test in `tests/manifest.json` under `profile=core`.
- Update `check_english_only_policy.py` to allow CJK only in the new locale file path.

## Decision log
- Decision: keep global English-only guardrail but add a single-path locale exception.
  - Reason: user requirement needs zh copy; broad policy rollback would damage prompt hygiene.
  - Rejected: removing English-only policy or allowing CJK across all docs.
- Decision: store localized onboarding copy in a dedicated locale file.
  - Reason: deterministic enforcement and easier expansion to future locales.

## Rollback plan
- Revert locale asset and contract changes:
  - `git revert` commit(s) that add locale file and policy exception.
- Restore previous branding/skill docs.
- Regenerate `FILE_INDEX` and `TEST_MATRIX`.
- Re-run:
  - `./.venv/bin/python tests/contract/check_english_only_policy.py`
  - `./.venv/bin/python tests/contract/check_onboarding_banner_locale_contract.py`

## Outcomes & retrospective (fill when done)
- Implemented richer onboarding banner card and controlled zh-CN locale support.
- Preserved deterministic policy enforcement via explicit contract coverage.
- Added a dedicated onboarding banner/locale contract test and registered it in core profile.
- Verified:
  - `./.venv/bin/python tests/run.py --profile core`
  - `./.venv/bin/python tests/run.py --profile nightly`
  - `lake build`
