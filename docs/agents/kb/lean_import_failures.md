# Common Lean import / naming failures

> This entry starts as a placeholder and should be driven by real Phase6 patterns.

## Symptoms
- `unknown constant` / `unknown namespace`
- `failed to synthesize` where the real root cause is a missing import

## Reproduction

```bash
lake build Problems/<slug>/Proof.lean
# or
lake build Problems.<slug>.Proof
```

## Fix playbook
1) Check whether mathlib already defines the name (LSP search or local grep).
2) Check Toolbox/Seeds (prefer same domain first).
3) Only if the name truly does not exist, write a local lemma.

## Regression check
- After adding the missing imports (or changing to the correct name), rerun:

```bash
lake build Problems.<slug>.Proof
```

- Ensure no new unused imports are introduced (optional): run `lake shake` or `#min_imports` audit in maintainer flows.
