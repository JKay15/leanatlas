# tools/deps (external dependency pins)

This directory stores **machine-readable** external dependency pins.
Human-readable install/verify instructions live in `docs/setup/**`.

## What is pins.json?

`pins.json` is the single source of truth for external dependency pinning:
- every dependency must declare: purpose / install / verify / pin
- contract tests check consistency with `docs/setup/**`
- any bump must go through a PR (auditable, rollbackable)

## Why this exists

Because drifting sources like `tool@latest` or `git@main` will eventually explode on some random day.

LeanAtlas’s goal is **reproducible proof loops**:
- same repo state + same pinned environment ⇒ same gates and outcomes

## Python note (uv standard)

LeanAtlas does not treat `requirements.txt` as the truth source.
Instead:
- `pyproject.toml`: direct dependency declarations
- `uv.lock`: full resolution lock (including transitive deps)

`uv.lock` must be committed.
Dependency bumps must explicitly run `uv lock` and go through PR review.
