# LeanAtlas branding (string-printable onboarding visuals)

LeanAtlas is designed to feel **product-like** when opened in the Codex App.

This file defines the **string-printable** onboarding visuals used by first-run routing.

Design goal: a high-clarity terminal onboarding card with a branded hero area and an instruction panel.

## Hero banner (v2)

Recommended for modern terminals.

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│  ██╗     ███████╗ █████╗ ███╗   ██╗ █████╗ ████████╗██╗      █████╗ ███████╗ │
│  ██║     ██╔════╝██╔══██╗████╗  ██║██╔══██╗╚══██╔══╝██║     ██╔══██╗██╔════╝ │
│  ██║     █████╗  ███████║██╔██╗ ██║███████║   ██║   ██║     ███████║███████╗ │
│  ██║     ██╔══╝  ██╔══██║██║╚██╗██║██╔══██║   ██║   ██║     ██╔══██║╚════██║ │
│  ███████╗███████╗██║  ██║██║ ╚████║██║  ██║   ██║   ███████╗██║  ██║███████║ │
│  ╚══════╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═══╝╚═╝  ╚═╝   ╚═╝   ╚══════╝╚═╝  ╚═╝╚══════╝ │
│                                                                              │
│                           ⚡ Powered by LeanAtlas ⚡                          │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Onboarding info panel (v2)

```text
+------------------------------------------------------------------------------+
| [i] Welcome to LeanAtlas                                                     |
+------------------------------------------------------------------------------+
| LeanAtlas first-run onboarding is ready.                                     |
|                                                                              |
| Choose one option before setup runs:                                         |
| • A) Full maintainer initialization (INIT_FOR_CODEX.md) [Recommended]        |
| • B) Python-only setup (.venv + core contracts)                              |
| • C) Skip setup and continue                                                  |
|                                                                              |
| Operational gate: install/verify active automations before normal tasks.     |
+------------------------------------------------------------------------------+
```

## Fallback (ASCII-only)

Use this if your terminal does not render box drawing or block characters consistently.

```text
+------------------------------------------------------------------------------+
| LEANATLAS :: Powered by LeanAtlas                                            |
+------------------------------------------------------------------------------+
| [i] Welcome to LeanAtlas                                                     |
| Choose: A) Full init (Recommended)  B) Python-only  C) Skip                  |
| Operational gate: install/verify active automations before normal tasks.     |
+------------------------------------------------------------------------------+
```

## Compact mark

```text
LEANATLAS :: Powered by LeanAtlas
```

## Where it is used

- First-run onboarding visual:
  - `.agents/skills/leanatlas-onboard/SKILL.md`
- Locale-specific zh-CN onboarding visual:
  - `docs/agents/locales/zh-CN/ONBOARDING_BANNER.md`

If you want to change onboarding visuals, edit the onboarding skill and keep this file in sync.
