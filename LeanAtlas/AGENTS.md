# LeanAtlas/AGENTS.md — System code rules

This directory will contain Toolbox/Incubator/Kernel code.

## OPERATOR mode
Treat everything under `LeanAtlas/**` as read-only. If a change seems needed, TRIAGE and propose a MAINTAINER ExecPlan.

## MAINTAINER mode
Changes here are high impact:
- Prefer adding reusable tools under Incubator/Seeds first.
- Promotion to Toolbox must follow gate + dedup + evidence.
- Any API change must be accompanied by:
  - updated retrieval rules
  - updated tests and a migration note
