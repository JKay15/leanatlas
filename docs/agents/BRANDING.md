# LeanAtlas branding (string-printable logo)

LeanAtlas is designed to feel **product-like** when opened in the Codex App.

This file defines the **string-printable** LeanAtlas logo used by onboarding.

Design goal: a Bauhaus-inspired, geometric mark that renders cleanly in a monospaced terminal.

## Primary logo (Unicode)

Recommended for modern terminals.

```text
       □   △   ○
┌──────────────────────┐
│  L E A N  A T L A S  │
└──────────────────────┘
```

Notes:

- The mark is built from three Bauhaus primitives: **square**, **triangle**, **circle**.
- The wordmark is spaced for a calm, “exhibit label” feel.
- Keep the exact spacing; terminals are monospaced.

## Fallback logo (ASCII-only)

Use this if your terminal cannot render `□△○` or box drawing characters consistently.

```text
       []  /\  ()
+----------------------+
|  L E A N  A T L A S  |
+----------------------+
```

## Compact mark

For very narrow consoles:

```text
□ △ ○  LEANATLAS
```

## Where it is used

- First-run onboarding banner:
  - `.agents/skills/leanatlas-onboard/SKILL.md`

If you want to change the banner, edit the onboarding skill and keep this file in sync.
