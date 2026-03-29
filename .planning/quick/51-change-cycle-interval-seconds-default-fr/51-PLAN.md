---
plan: "51-01"
goal: "Change cycle_interval_seconds default from 5 to 0.5 (500ms) for crypto pair paper mode"
mode: quick
---

# Quick Task 051: cycle_interval_seconds default 5 → 0.5

## Task 1: Update type and default in all locations

**Files:**
- `packages/polymarket/crypto_pairs/paper_runner.py`
- `tools/cli/crypto_pair_run.py`
- `tools/gates/tape_integrity_audit.py`

**Action:**
1. `paper_runner.py:125`: `cycle_interval_seconds: int = 5` → `cycle_interval_seconds: float = 0.5`
2. `paper_runner.py:300`: `int(payload.get("cycle_interval_seconds", 5))` → `float(payload.get("cycle_interval_seconds", 0.5))`
3. `crypto_pair_run.py:273`: `Optional[int]` → `Optional[float]`
4. `crypto_pair_run.py:81`: argparse `type=int` → `type=float`, help text `or 5` → `or 0.5`
5. `tape_integrity_audit.py:_get_runner_scan_cadence()`: return type `Optional[int]` → `Optional[float]`, match `float` in line, use `float(val_str)`

**Verify:** `asyncio.sleep(0.5)` works natively — no integer casting in the sleep path at line 696.

**Done:** `2767 passed, 0 failed`
