# mk_poly_factorization_square (fixture)

This fixture represents a low-level, highly reusable algebra fact:

- It is small enough to be a **unit test** for the proof-loop.
- It is realistic enough that the agent has to navigate the polynomial API.

In later phases, solving several polynomial tasks should allow the system to extract and reuse
small helper lemmas (e.g. `sq_sub_sq`) rather than re-proving them.
