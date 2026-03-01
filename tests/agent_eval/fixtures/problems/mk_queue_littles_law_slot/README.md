# mk_queue_littles_law_slot (fixture)

This fixture isolates the **combinatorial core** of Little's law:

- It does *not* assume stochastic arrival/service processes.
- It proves an identity by double counting a finite indicator matrix.

This is intentionally chosen because:
- it is classical (well-known),
- it is fully deterministic and audit-friendly,
- it stress-tests Lean's finite-sum algebra and the agent's ability to pick the right lemmas.
