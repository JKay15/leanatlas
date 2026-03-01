# Reuse (do not reinvent wheels)

LeanAtlas’s core value is to convert Codex work from “reinventing wheels” into:

- assembling mature wheels (community tools, existing best practices), and
- filling only the unavoidable gaps.

This directory records:
- which external projects/tools we can reuse (and why they are mature enough)
- how to integrate them into LeanAtlas (install/verify/version pin/downgrade)
- where no mature wheel exists yet (LeanAtlas must implement minimal glue)

Note: this is an engineering instruction set for maintainers and Codex, not marketing.

Entry points:
- `GC_REUSE.md`: reusable wheels for the GC loop
