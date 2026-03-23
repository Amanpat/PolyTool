---
phase: quick-019
plan: 01
subsystem: crypto_pairs
tags: [backtest, harness, accumulation-engine, phase-1a, cli]
dependency_graph:
  requires:
    - packages/polymarket/crypto_pairs/accumulation_engine.py
    - packages/polymarket/crypto_pairs/fair_value.py
    - packages/polymarket/crypto_pairs/paper_runner.py
    - packages/polymarket/crypto_pairs/reference_feed.py
  provides:
    - packages/polymarket/crypto_pairs/backtest_harness.py
    - tools/cli/crypto_pair_backtest.py
  affects:
    - polytool/__main__.py
tech_stack:
  added: []
  patterns:
    - TDD (RED-GREEN, tests written before implementation)
    - pure-function replay engine (no network, no filesystem I/O in harness)
    - JSONL observation input with optional per-record fair-value params
    - dated artifact directory layout matching position_store convention
key_files:
  created:
    - packages/polymarket/crypto_pairs/backtest_harness.py
    - tests/test_crypto_pair_backtest.py
    - tools/cli/crypto_pair_backtest.py
    - docs/features/FEATURE-crypto-pair-backtest-v0.md
    - docs/dev_logs/2026-03-23_phase1a_crypto_pair_backtest_v0.md
  modified:
    - polytool/__main__.py
decisions:
  - "Added yes_accumulated_size / no_accumulated_size to BacktestObservation to allow partial-pair state simulation; without them soft_rule_blocked_all_legs is mathematically unreachable in stateless replay due to complement constraint (fair_yes + fair_no = 1)"
  - "Fresh feed snapshot uses price=1.0 sentinel when underlying_price is None; feed gate ignores the price value, only is_stale and connection_state matter"
  - "Soft fair-value filter disabled (vacuous pass) when any of underlying_price, threshold, remaining_seconds is absent"
metrics:
  duration: ~30 minutes (active execution; plan continuation from prior session)
  completed_date: 2026-03-23
  tasks_completed: 2
  files_created: 5
  files_modified: 1
  tests_added: 22
---

# Phase quick-019 Plan 01: Crypto Pair Backtest Harness v0 Summary

**One-liner:** Deterministic JSONL-driven backtest harness replaying observations through accumulation engine with lognormal fair-value filter; CLI emits manifest/summary/report artifacts per dated run.

## What Was Built

### Task 1: BacktestHarness pure replay engine (commit: 5aeaafc)

`packages/polymarket/crypto_pairs/backtest_harness.py` — pure-function replay loop.
`tests/test_crypto_pair_backtest.py` — 22 deterministic offline tests.

The harness accepts a list of `BacktestObservation` records, builds synthetic
`ReferencePriceSnapshot` objects, optionally calls `estimate_fair_value()`, routes
each `AccumulationIntent` to the correct skip counter, and returns a `BacktestResult`
with per-category counts and pair cost metrics.

Key types:
- `BacktestObservation` — frozen dataclass with optional accumulated sizes for partial-pair simulation
- `BacktestResult` — metrics container with `to_dict()` for JSON output
- `BacktestHarness` — stateless, `run(list[BacktestObservation]) -> BacktestResult`

### Task 2: CLI entrypoint and docs (commit: c1a57de)

`tools/cli/crypto_pair_backtest.py` — `build_parser()` + `main(argv)`.  Reads JSONL,
applies symbol/duration filters, runs `BacktestHarness`, writes three artifacts.

`polytool/__main__.py` — registered `crypto-pair-backtest` command.

`docs/features/FEATURE-crypto-pair-backtest-v0.md` — full input contract, metrics
definitions, gate hierarchy, soft_rule_skips reachability note, CLI examples.

`docs/dev_logs/2026-03-23_phase1a_crypto_pair_backtest_v0.md` — mandatory dev log.

## Verification Results

```
python -m pytest tests/test_crypto_pair_backtest.py tests/test_crypto_pair_accumulation_engine.py tests/test_crypto_pair_fair_value.py -q
104 passed, 0 failed
```

```
python -m polytool crypto-pair-backtest --help
# exits 0, shows --input, --output, --symbol, --market-duration, --run-id
```

Synthetic 3-observation spot-check:
- 1 intent (0.47+0.48=0.95, passes hard rule, no fair-value filter)
- 1 hard_rule_skip (0.51+0.51=1.02 > 0.97)
- 1 feed_stale_skip
- manifest.json, summary.json, report.md all written to dated artifact dir

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] soft_rule_blocked_all_legs unreachable in stateless replay**
- **Found during:** Task 1 GREEN phase (test failed after implementation)
- **Issue:** Test `test_soft_rule_blocks_all_legs_counts_as_soft_rule_skip` asserted
  `soft_rule_skips == 1` but got 0.  Root cause: the lognormal model enforces
  `fair_yes + fair_no = 1.0`, so blocking both legs via soft rule requires
  `yes_ask + no_ask > 1.0`, which always triggers the hard rule first (threshold=0.97).
  With the test's `yes_ask=0.60, no_ask=0.35`, `no_ask=0.35 < fair_no=0.5` so the
  NO leg actually passed the soft rule, yielding a partial intent instead of a skip.
- **Fix:** Added `yes_accumulated_size: float = 0.0` and `no_accumulated_size: float = 0.0`
  to `BacktestObservation`.  Updated `PairMarketState` construction in `run()` to use
  these values.  Rewrote the test to use `yes_accumulated_size=1.0` (yes_only partial
  state) with `yes_ask=0.36, no_ask=0.60` (pair=0.96 ≤ 0.97, no_ask > fair_no=0.5).
  In yes_only state `_select_legs()` returns NO only; NO soft rule fails → empty legs
  → `soft_rule_blocked_all_legs` → `soft_rule_skips += 1`.
- **Files modified:** `backtest_harness.py`, `test_crypto_pair_backtest.py`
- **Commit:** 5aeaafc (included in the GREEN commit)

## Self-Check: PASSED

Files exist:
- packages/polymarket/crypto_pairs/backtest_harness.py — FOUND
- tests/test_crypto_pair_backtest.py — FOUND
- tools/cli/crypto_pair_backtest.py — FOUND
- docs/features/FEATURE-crypto-pair-backtest-v0.md — FOUND
- docs/dev_logs/2026-03-23_phase1a_crypto_pair_backtest_v0.md — FOUND

Commits:
- 5aeaafc — feat(quick-019): implement BacktestHarness pure replay engine — FOUND
- c1a57de — feat(quick-019): add crypto-pair-backtest CLI and register command — FOUND
