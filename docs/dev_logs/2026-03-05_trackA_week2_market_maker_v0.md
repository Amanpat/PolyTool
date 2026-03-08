# Track A Week 2 — MarketMakerV0 + OrderManager

**Date:** 2026-03-05
**Branch:** simtrader
**Specs:** docs/specs/SPEC-0010-simtrader-vision-and-roadmap.md, docs/specs/SPEC-0011-live-execution-layer.md

---

## Summary

Implemented the two core Week 2 primitives for the live execution layer:
1. **MarketMakerV0** — a conservative two-sided quoting strategy (pure + testable)
2. **OrderManager** — reconciliation loop diffing desired vs. open orders with churn limits

Both are wired into:
- The existing `StrategyRunner` replay/shadow path (via `STRATEGY_REGISTRY` in `strategy/facade.py`)
- The `simtrader live` CLI (via new `--strategy market_maker_v0` flag)

All 71 new tests pass; full suite: 1174 passed.

---

## Files Touched

### New

| File | Purpose |
|------|---------|
| `packages/polymarket/simtrader/strategies/market_maker_v0.py` | `MarketMakerV0` strategy |
| `packages/polymarket/simtrader/execution/order_manager.py` | `OrderManager` reconciliation loop |
| `tests/test_market_maker_v0.py` | 48 tests for strategy |
| `tests/test_order_manager.py` | 23 tests for OrderManager |
| `docs/dev_logs/2026-03-05_trackA_week2_market_maker_v0.md` | This file |

### Modified

| File | Change |
|------|--------|
| `packages/polymarket/simtrader/strategy/facade.py` | Registered `market_maker_v0` in `STRATEGY_REGISTRY` |
| `tools/cli/simtrader.py` | Added `--strategy`, `--best-bid`, `--best-ask`, `--asset-id`, `--inventory-units`, `--mm-tick-size`, `--mm-order-size` to `live` subparser; updated `_live()` handler |

---

## Design Decisions

### MarketMakerV0 quoting model

```
bid_base = best_bid - quote_ticks_from_bbo * tick_size
ask_base = best_ask + quote_ticks_from_bbo * tick_size

skew_adj = clamp(-inventory * skew_factor, -max_skew_ticks, +max_skew_ticks) * tick_size

bid_raw = bid_base + skew_adj
ask_raw = ask_base + skew_adj

bid_price = tick_floor(bid_raw)
ask_price = tick_ceil(ask_raw)
```

- `quote_ticks_from_bbo=0` (default): quote AT the BBO.
- Positive inventory (long): `skew_adj < 0` → both quotes shift DOWN → ask more competitive (sell), bid less competitive (buy less).
- Negative inventory (short): `skew_adj > 0` → both quotes shift UP → bid more competitive (buy), ask less competitive.
- `max_skew_ticks` clamps the skew so extreme inventory cannot push prices to nonsensical values.

### Guards (any → no quotes emitted)

1. `best_bid` or `best_ask` is None (empty/stale book)
2. `best_bid >= best_ask` (crossed book)
3. `order_size < min_order_size`
4. `bid_price <= 0` or `ask_price >= 1` (binary market bounds)
5. `bid_price >= ask_price` (computed quotes would cross)

All guards are silent (log DEBUG); they never raise.

### Replay integration

Registered as `"market_maker_v0"` in `STRATEGY_REGISTRY`.  Usage:

```bash
python -m polytool simtrader run \
  --tape artifacts/simtrader/tapes/.../events.jsonl \
  --strategy market_maker_v0 \
  --strategy-config-json '{"tick_size": "0.01", "order_size": "10"}'
```

The `StrategyRunner` calls `on_start` / `on_event` / `on_fill` / `on_finish` exactly as for any other strategy.  The strategy manages its own inventory position from fills.

### Shadow integration

Because `MarketMakerV0` implements the standard `Strategy` interface, it also works with `ShadowRunner` transparently — no extra wiring needed.

### OrderManager design

- **Diff by (asset_id, side)**: each side is an independent slot; at most one desired quote per slot.
- **Cancel stale**: if an open order's price doesn't match the desired price, it is cancelled (subject to min-lifetime and rate cap).
- **Place new**: if no open order matches the desired slot, place a new order.
- **Keep matching**: if open order price == desired price, no action.
- **Min-lifetime guard**: orders younger than `min_order_lifetime_seconds` (default 5s) are not cancelled — prevents wasteful churn when quotes oscillate.
- **Rate caps**: sliding 60-second window for both cancels and places (`max_cancels_per_minute`, `max_places_per_minute`).  Excess actions are skipped and counted in `ActionPlan.skipped_*`.
- **Injectable clock**: `_clock` param for deterministic testing without real sleeps.

### CLI live + market_maker_v0

```bash
python -m polytool simtrader live \
  --strategy market_maker_v0 \
  --best-bid 0.45 \
  --best-ask 0.55 \
  --asset-id mytoken \
  --inventory-units 5
```

In dry-run mode (default):
- Prints `WOULD PLACE BUY/SELL <price> <size>` lines to stderr for each quote
- Runs OrderManager reconcile against empty open_orders (one-shot tick)
- Passes quotes through `LiveRunner.run_once()` → risk checks → executor (no client call)
- Prints JSON summary to stdout

---

## Test Coverage

```
tests/test_market_maker_v0.py — 48 tests
  TestTickHelpers              6  (floor/ceil math)
  TestMarketMakerV0Constructor 5  (defaults, validation)
  TestEmptyBook                5  (None/crossed book)
  TestNormalQuoting           10  (intent shape, sides, prices)
  TestTickAlignment            3  (floor/ceil of raw prices)
  TestNoCrossSpread            3  (bid < ask always)
  TestInventorySkew            5  (direction, clamping)
  TestPriceRangeGuard          2  (binary bounds)
  TestStrategyLifecycle        6  (on_start/on_event/on_fill)
  TestComputeOrderRequests     3  (live bridge)

tests/test_order_manager.py — 23 tests
  TestIsOldEnough              3  (age check)
  TestBasicReconcile           6  (place/keep/cancel/replace)
  TestMinLifetime              4  (churn protection)
  TestRateCaps                 4  (cancel/place caps, window reset)
  TestActionPlanStability      2  (determinism)
  TestActionPlanDefaults       2  (dataclass)
  TestMultiAsset               2  (per-asset independence)
```

---

## pytest Output

```
===================== 1174 passed, 25 warnings in 50.84s ======================
```

(71 new tests; 1103 existing all still green.)

---

## Open Questions

1. **OrderManager ↔ LiveExecutor integration** — `reconcile_once` returns an `ActionPlan` (to_cancel, to_place) but the current `_live()` CLI only uses `to_place` for display; `to_cancel` is not yet wired to `executor.cancel_order`. This is intentional for a one-shot tick at Stage 0 with empty open_orders; needs wiring when persistent order state is tracked.

2. **Inventory persistence across ticks** — `MarketMakerV0._inventory` resets on `on_start`. For the `simtrader live` CLI (which creates a fresh strategy per invocation), the operator must supply `--inventory-units` from external state. A persistent state file per session will be needed for multi-tick operation.

3. **Tick size discovery** — the strategy requires the operator to supply `--mm-tick-size`. In replay/shadow mode, the tick_size could be auto-detected from `tick_size_change` events; this auto-detection is not yet implemented.

4. **Quote replacement vs. amendment** — the current design always cancels + re-places when prices change. Some exchanges support order amendment (reduce latency and avoid losing queue position). Not relevant for Stage 0 dry-run but worth noting for Stage 1+.
