# ExecPlan: Strong-Guarantee Pack (Promotion Lint + Force Deposit)

Date: 2026-02-28  
Mode: MAINTAINER  
Owner: Codex (local workspace)

## 1) Scope

This plan hardens three areas that were identified as gaps:

1. Promotion verification must include `lake lint` (contract alignment).
2. Rule-of-Three exception path must be test-covered and auditable.
3. User-specified force-deposit must be supported for:
   - tools (promotion reuse gate)
   - skills (KB suggestion mining)
   - feedback (chat feedback deposition)

## 2) Files to change

- `tools/promote/promote.py`
- `tools/bench/mine_kb_suggestions.py`
- `tools/feedback/mine_chat_feedback.py`
- `tools/index/force_deposit.json` (new truth source)
- `tests/contract/check_force_deposit_policy.py` (new gate)
- `tests/manifest.json`
- `docs/testing/TEST_MATRIX.md` (generated)
- `docs/contracts/PROMOTION_GATE_CONTRACT.md`
- `docs/contracts/SKILLS_GROWTH_CONTRACT.md`
- `docs/contracts/FEEDBACK_GOVERNANCE_CONTRACT.md`
- `docs/navigation/FILE_INDEX.md` (generated)

## 3) Milestones

### M1: Add force-deposit policy gate (tests first)

- Add a contract test that verifies:
  - Promotion force-deposit behavior (with and without justification).
  - KB mining force-deposit behavior under high thresholds.
  - Feedback miner force-deposit behavior with empty inbox.
  - Promotion verification path contains `lake lint`.

Acceptance:
- New test fails on old behavior and passes after implementation.

### M2: Implement code changes

- Promotion:
  - Add `lake lint` to verification gate.
  - Add auditable force-deposit bypass with mandatory justification.
- KB mining:
  - Read optional force signatures from force-deposit truth source.
  - Emit forced suggestions even below default thresholds.
- Feedback miner:
  - Read optional forced feedback items from force-deposit truth source.
  - Keep transcript filtering behavior unchanged.

Acceptance:
- Behavior matches M1 tests.

### M3: Register and validate

- Register new test in `tests/manifest.json`.
- Regenerate `docs/testing/TEST_MATRIX.md`.
- Regenerate `docs/navigation/FILE_INDEX.md`.
- Update contracts to document new knobs.

Acceptance:
- `tests/contract/check_test_registry.py` passes.
- `tests/contract/check_test_matrix_up_to_date.py` passes.
- `tests/contract/check_file_index_reachability.py` passes.

### M4: Full core verification

Run:

```bash
./.venv/bin/python tests/run.py --profile core
```

Acceptance:
- Core tier passes.

## 4) Rollback points

- Revert this plan’s touched files as one slice.
- If needed, keep only `lake lint` addition and roll back force-deposit features independently.

