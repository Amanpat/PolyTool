---
phase: quick-046
plan: 46
subsystem: crypto-pairs
tags: [strategy, accumulation-engine, config, paper-runner, ledger, event-models]

# Dependency graph
requires:
  - phase: quick-040
    provides: paper runner, position store, reference feed, live execution wiring
provides:
  - Per-leg target-bid gate replacing broken pair-cost gate
  - edge_buffer_per_leg config (default 0.04 => target_bid = 0.46)
  - accumulation_engine ACCUMULATE/PARTIAL/FREEZE/SKIP actions
  - target_bid_computed runtime event emitted each cycle
  - Backward compat: old target_pair_cost_threshold key silently ignored on load
affects: [quick-047, quick-048, live-deployment, backtest-harness]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Per-leg target-bid gate: target_bid = 0.5 - edge_buffer_per_leg (fair value always falls back to 0.5 in paper mode)"
    - "Optional[Decimal] = None pattern in frozen dataclasses to retire required fields while preserving ClickHouse schema columns"
    - "build_market_rollups() uses constant threshold_pass_count=len(observations_list) since all observations now implicitly pass"

key-files:
  created: []
  modified:
    - packages/polymarket/crypto_pairs/config_models.py
    - packages/polymarket/crypto_pairs/accumulation_engine.py
    - packages/polymarket/crypto_pairs/paper_runner.py
    - packages/polymarket/crypto_pairs/paper_ledger.py
    - packages/polymarket/crypto_pairs/event_models.py
    - packages/polymarket/crypto_pairs/live_runner.py
    - packages/polymarket/crypto_pairs/backtest_harness.py
    - packages/polymarket/crypto_pairs/dev_seed.py
    - tools/cli/crypto_pair_backtest.py
    - tests/test_crypto_pair_accumulation_engine.py
    - tests/test_crypto_pair_backtest.py
    - tests/test_crypto_pair_clickhouse_sink.py
    - tests/test_crypto_pair_live_safety.py
    - tests/test_crypto_pair_paper_ledger.py
    - tests/test_crypto_pair_run.py
    - tests/test_crypto_pair_runner_events.py

key-decisions:
  - "Replace target_pair_cost_threshold (always fired at >=0.99 on real markets) with per-leg target_bid = 0.5 - edge_buffer_per_leg (default 0.46)"
  - "fair value always falls back to 0.5 in paper mode since PairOpportunity carries no threshold/remaining_seconds; this is expected behavior, not a bug"
  - "Retire target_pair_cost_threshold as Optional[Decimal] = None in event_models to preserve ClickHouse schema backward compat without requiring a migration"
  - "test prices updated from 0.47/0.48 to 0.44/0.44 in tests that assert intent/order creation (both > target_bid 0.46 before, both below after)"

patterns-established:
  - "Per-leg gate pattern: each leg evaluated independently; ACCUMULATE if any leg qualifies"
  - "Backward compat pattern: from_dict() silently ignores removed config keys; old keys accepted but not applied"

requirements-completed: [QUICK-046]

# Metrics
duration: 120min
completed: 2026-03-29
---

# Phase quick-046: Strategy Pivot to Per-Leg Target-Bid Gate Summary

**Replaced broken pair-cost gate (sum >= 0.99 always failed) with per-leg target-bid gate: `target_bid = 0.5 - edge_buffer_per_leg` (default 0.46), unblocking intent generation in both paper and live modes.**

## Performance

- **Duration:** ~120 min
- **Completed:** 2026-03-29T18:06:55Z
- **Tasks:** 4
- **Files modified:** 16

## Accomplishments

### Task 1 — Config model pivot

Removed `target_pair_cost_threshold` from `CryptoPairPaperModeConfig` and added three new fields:
- `edge_buffer_per_leg: Decimal = Decimal("0.04")`
- `max_pair_completion_pct: Decimal = Decimal("0.80")`
- `min_projected_profit: Decimal = Decimal("0.03")`

`from_dict()` silently ignores the old `target_pair_cost_threshold` key for backward compat. `__post_init__` validates: `0 < edge_buffer_per_leg < 0.5`, `0 < max_pair_completion_pct <= 1`, `min_projected_profit > 0`.

### Task 2 — Accumulation engine rewrite

`evaluate_accumulation()` now uses a per-leg target-bid gate instead of a projected pair-cost comparison. `target_bid_yes = fair_value_yes - edge_buffer` (falls back to `0.5 - edge_buffer = 0.46` when fair value unavailable). A leg qualifies when `ask_price <= target_bid`. Returns `ACTION_ACCUMULATE` if any leg qualifies, `ACTION_SKIP` otherwise. Removed `_soft_rule_passes()` and the pair-cost hard-rule. Kept `AccumulationIntent` fields `hard_rule_passed`, `soft_rule_yes_passed`, `soft_rule_no_passed`, `projected_pair_cost` for API compat.

### Task 3 — paper_runner, paper_ledger, event_models, live_runner cleanup

- `paper_runner.py`: removed `_OPERATOR_MAX_PAIR_COST`, updated `build_default_paper_mode_config()`, `CryptoPairRunnerSettings.__post_init__` validation, `build_runner_settings()` key list, `build_observation()` signature, and `_process_opportunity()` to emit `target_bid_computed` event and pass `target_yes_bid/target_no_bid` to `build_observation()`
- `paper_ledger.py`: removed orphaned `object.__setattr__(self, "target_pair_cost_threshold", ...)` from `PaperOrderIntent.__post_init__`; replaced `observation.threshold_passed` in `build_market_rollups()` with constants; `generate_order_intent()` uses `observation.target_yes_bid or observation.yes_quote_price` as intended price
- `event_models.py`: `target_pair_cost_threshold` and `threshold_edge_usdc` in `OpportunityObservedEvent` changed from required `Decimal` to `Optional[Decimal] = None`; same for `IntentGeneratedEvent.target_pair_cost_threshold`; `from_observation()` and `from_intent()` no longer pass these kwargs
- `live_runner.py`: removed `target_pair_cost_threshold=` kwarg from `build_observation()` call
- `tools/cli/crypto_pair_backtest.py`: updated report config label from `target_pair_cost_threshold` to `edge_buffer_per_leg`

### Task 4 — Full regression

All 2755 tests pass. Test prices updated from `(None, 0.47)/(None, 0.48)` to `(None, 0.44)/(None, 0.44)` in tests that assert intent or order creation, since both prices exceeded the new `target_bid = 0.46` and would have blocked the gate.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Orphaned setattr in PaperOrderIntent.__post_init__**
- **Found during:** Task 3 cleanup
- **Issue:** `object.__setattr__(self, "target_pair_cost_threshold", target_pair_cost_threshold)` referenced a variable that no longer existed after removing the field from `PaperOpportunityObservation`
- **Fix:** Removed the line from `paper_ledger.py` `PaperOrderIntent.__post_init__`
- **Files modified:** packages/polymarket/crypto_pairs/paper_ledger.py
- **Commit:** aa861dc

**2. [Rule 1 - Bug] build_market_rollups() used removed threshold_passed attribute**
- **Found during:** Task 3 cleanup
- **Issue:** `build_market_rollups()` referenced `observation.threshold_passed` which was removed from `PaperOpportunityObservation`
- **Fix:** Replaced the count with `threshold_pass_count=len(observations_list), threshold_miss_count=0` since with the new gate all observations are eligible
- **Files modified:** packages/polymarket/crypto_pairs/paper_ledger.py
- **Commit:** aa861dc

**3. [Rule 2 - Missing compat] event_models required fields broke serialization**
- **Found during:** Task 3 cleanup
- **Issue:** `OpportunityObservedEvent` and `IntentGeneratedEvent` had `target_pair_cost_threshold` and `threshold_edge_usdc` as required `Decimal` fields but `from_observation()` and `from_intent()` no longer passed them
- **Fix:** Changed to `Optional[Decimal] = None`; switched `_coerce_decimal` to `_coerce_optional_decimal` in `__post_init__`; removed kwargs from factory methods
- **Files modified:** packages/polymarket/crypto_pairs/event_models.py
- **Commit:** aa861dc

**4. [Rule 1 - Bug] live_runner.py still passed removed kwarg to build_observation()**
- **Found during:** Task 3 cleanup
- **Issue:** `build_observation()` signature no longer accepted `target_pair_cost_threshold=` kwarg
- **Fix:** Removed the kwarg from the call site in `live_runner.py`
- **Files modified:** packages/polymarket/crypto_pairs/live_runner.py
- **Commit:** aa861dc

**5. [Rule 1 - Bug] test prices above new target_bid gate**
- **Found during:** Task 4 regression
- **Issue:** `test_paper_default_path_creates_jsonl_bundle`, `test_runner_emits_heartbeat_event_and_callback`, and `test_live_disconnect_cancels_working_orders_and_requires_reconnect` used prices `(None, 0.47)/(None, 0.48)` which both exceed `target_bid = 0.46`, so no intents/orders were placed, causing assertions about created files and order cancellation to fail
- **Fix:** Updated CLOB prices to `(None, 0.44)/(None, 0.44)` in all three tests
- **Files modified:** tests/test_crypto_pair_run.py, tests/test_crypto_pair_live_safety.py
- **Commit:** aa861dc

## Known Stubs

None — all data flows are wired. `target_yes_bid` and `target_no_bid` are computed and passed through the full pipeline. Fair value always falls back to `0.5` in paper mode (expected; `PairOpportunity` carries no `threshold` or `remaining_seconds`).

## Self-Check: PASSED

- aa861dc exists: confirmed
- 16 files modified in commit: confirmed
- 2755 tests pass: confirmed
