# References collections

This directory holds **curated reference collections** used by LeanAtlas tests and agent-eval task packs.

Why this exists:

- Tasks and fixtures should cite *verifiable* sources.
- We want citations to be **stable and reusable** (don’t paste random links into many files).

## Files

- `mentor_keywords.yaml` — sources for the “mentor keyword classics” agent-eval pack.

## Rule

Agent-eval `task.yaml` files **must cite** sources from these collections using the `REF:<id>` convention.

Example:

```yaml
references:
  - "REF:TOPSOE_LOGBNDS"
  - "REF:BV_CVXBOOK_2004"
```

A CI check enforces:

- `references` is non-empty
- every `REF:<id>` exists in the relevant collection
