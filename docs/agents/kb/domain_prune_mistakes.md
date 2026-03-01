# Domain pruning mistakes (classic symptoms)

> This entry is intentionally short: “wrong pruning” is one of the most invisible failure modes.
> It looks like “the library has nothing”, but the truth is “you searched the wrong slice”.

## Symptoms
- RetrievalTrace shows a `DOMAIN_PRUNE` step that excluded the directory where the needed lemma actually lives.
- Repeated `NAME_NOT_FOUND` errors, but a full-repo search finds the lemma immediately.

## Safe downgrade strategy
1) Detect repeated `NAME_NOT_FOUND` of the same family for K attempts (K is a policy knob).
2) Downgrade: disable pruning for the next retrieval step (expand to full search).
3) Record the downgrade explicitly in RetrievalTrace (`fallback_used=true`). Never fail silently.
