# LeanAtlas/Incubator/Seeds

It is recommended that each subdirectory be bucketed by **domain_id**:

- `LeanAtlas/Incubator/Seeds/<domain_id>/**`

In this way, GC and retrieval pruning can directly reuse the directory structure (without additional indexes).
