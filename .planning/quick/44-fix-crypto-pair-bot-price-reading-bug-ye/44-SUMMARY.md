---
phase: quick-044
plan: 01
subsystem: crypto_pairs
tags: [clob, price_bug, get_best_bid_ask, crypto_pair_bot]

# Dependency graph
requires: []
provides:
  - packages/polymarket/clob.py (get_best_bid_ask fixed: min() over all ask levels)
  - packages/polymarket/crypto_pairs/opportunity_scan.py (DEBUG log added)
  - tests/test_clob.py (4 new tests: TestGetBestBidAsk)
affects: [crypto_pair_bot_opportunity_scan, paired_cost_accuracy]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "best_ask = min(...) over all ask levels because Polymarket /book endpoint returns asks sorted DESC"
    - "bids[0] remains correct — DESC sort means bids[0] is highest bid"

key-files:
  modified:
    - packages/polymarket/clob.py
    - packages/polymarket/crypto_pairs/opportunity_scan.py
    - tests/test_clob.py

key-decisions:
  - "Use min() not asks[0]: Polymarket CLOB returns asks descending (worst-first), so index-zero was always returning ~$0.99"
  - "bids[0] unchanged: bids also sorted DESC so bids[0] is best (highest) bid — no bug there"
  - "DEBUG log added in compute_pair_opportunity() to surface real prices per cycle"

patterns-established:
  - "Polymarket /book endpoint: asks sorted DESC (highest price first), bids sorted DESC (highest price first)"

requirements-completed: []

# Metrics
duration: ~30m
completed: 2026-03-29
---

# quick-044: Fix crypto pair bot price reading bug

**`get_best_bid_ask()` was returning ~$0.99 for every ask token because Polymarket sorts asks descending; fix uses `min()` over all ask levels; 4 new tests, 2753 passing**

## Performance

- **Duration:** ~30 minutes
- **Completed:** 2026-03-29
- **Commit:** b257165

## Accomplishments

- Fixed `get_best_bid_ask()` in `packages/polymarket/clob.py`: replaced `asks[0]` with `min()` over all ask price levels
- Added `logger.debug` in `compute_pair_opportunity()` for price verification
- Added 4 new unit tests in `tests/test_clob.py::TestGetBestBidAsk` covering: asks DESC, asks ASC, empty asks, empty bids
- 2753 tests passing, 0 regressions

## Root Cause

The Polymarket CLOB `/book` endpoint returns asks sorted **descending** (highest price first). `asks[0]` was always returning the worst (most expensive) ask (~$0.99), making `paired_cost = $1.98` on every cycle — so the bot never found an opportunity.

`bids[0]` is correct: bids are also sorted descending so `bids[0]` is the highest (best) bid, which is what we want.

## Files Modified

- `packages/polymarket/clob.py` — `min(...)` fix in `get_best_bid_ask()`
- `packages/polymarket/crypto_pairs/opportunity_scan.py` — DEBUG log in `compute_pair_opportunity()`
- `tests/test_clob.py` — `TestGetBestBidAsk` (4 tests)

## Deviations from Plan

None.

---
*Phase: quick-044*
*Completed: 2026-03-29*
