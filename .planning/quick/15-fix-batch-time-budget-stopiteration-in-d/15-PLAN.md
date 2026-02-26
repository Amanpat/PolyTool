# Quick Task 15 — Fix batch time_budget StopIteration in Docker

## Goal
Refactor `run_batch` loop in `batch/runner.py` so the time budget is checked
BEFORE the next candidate is fetched, and wrap candidate retrieval in
`try/except StopIteration` to prevent any StopIteration from escaping.

## Root Cause
The current `for idx, resolved in enumerate(markets)` loop fetches each market
from the iterator BEFORE the budget check executes. If the candidate source
were a generator (or if a future refactor adds more `time.monotonic()` calls
before the break), a StopIteration could escape the loop body and produce
confusing failures in Docker (Python 3.11).

The test mock uses `side_effect=[0.0, 0.0, 11.0]` — exactly 3 values for
exactly 3 `time.monotonic()` calls. A 4th call (possible under refactoring)
would raise StopIteration inside the for-loop body, which may silently
terminate the loop instead of propagating the exception.

## Fix

### Task 1 — Refactor `run_batch` loop in `packages/polymarket/simtrader/batch/runner.py`

**File:** `packages/polymarket/simtrader/batch/runner.py`

Replace the for-loop (lines ~240-261) with an explicit while loop:

```python
# BEFORE
for idx, resolved in enumerate(markets):
    if params.time_budget_seconds is not None:
        elapsed = time.monotonic() - batch_start_monotonic
        if elapsed >= params.time_budget_seconds:
            remaining = markets[idx:]
            print(...)
            for pending in remaining:
                rows.append(_time_budget_skipped_row(pending))
            break
    row = _run_market(...)
    rows.append(row)

# AFTER
market_iter = iter(markets)
while True:
    # Check budget BEFORE fetching the next candidate
    if params.time_budget_seconds is not None:
        elapsed = time.monotonic() - batch_start_monotonic
        if elapsed >= params.time_budget_seconds:
            remaining = list(market_iter)
            print(
                "[batch] time budget exhausted "
                f"({elapsed:.1f}s >= {params.time_budget_seconds:.1f}s); "
                f"skipping {len(remaining)} remaining market(s).",
                file=sys.stderr,
            )
            for pending in remaining:
                rows.append(_time_budget_skipped_row(pending))
            break
    try:
        resolved = next(market_iter)
    except StopIteration:
        break
    row = _run_market(
        resolved=resolved,
        params=params,
        markets_dir=markets_dir,
        sweep_config=sweep_config,
        ts=ts,
    )
    rows.append(row)
```

**Verify:** `pytest -q tests/test_simtrader_batch.py -k time_budget` passes
**Done:** All 3 time_budget tests pass locally and in Docker

## Commit
`fix(batch): check time budget before fetching next candidate; wrap next() in try/except StopIteration`
