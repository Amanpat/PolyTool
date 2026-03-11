## Summary

Track A Week 2 shipped two primitives that complete the order lifecycle layer:

- `MarketMakerV0` — conservative two-sided quoting strategy
- `OrderManager` — reconciliation loop that diffs desired vs. open orders

Both are wired into replay (`simtrader run`), shadow (`simtrader shadow`), and
dry-run live (`simtrader live`) via the `--strategy market_maker_v0` flag.

## What shipped

### MarketMakerV0 (`packages/polymarket/simtrader/strategies/market_maker_v0.py`)

A conservative two-sided quoting strategy for Polymarket binary markets.

**Quoting model:**

```
bid_price = tick_floor(best_bid - quote_ticks_from_bbo * tick_size + skew_adj)
ask_price = tick_ceil(best_ask + quote_ticks_from_bbo * tick_size + skew_adj)

skew_adj = clamp(-inventory_units * inventory_skew_factor, -max_skew_ticks, +max_skew_ticks) * tick_size
```

Defaults: `quote_ticks_from_bbo=0` (quote AT BBO), `inventory_skew_factor=0.5`,
`tick_size=0.01`, `order_size=10`.

**Guards (any failure → no quotes emitted, silent):**
1. `best_bid` or `best_ask` is None (empty/stale book)
2. `best_bid >= best_ask` (crossed book)
3. `bid_price >= ask_price` (computed quotes would cross)
4. `bid_price <= 0` or `ask_price >= 1` (binary market bounds violated)
5. `order_size < min_order_size`

### OrderManager (`packages/polymarket/simtrader/execution/order_manager.py`)

Reconciles the strategy's `desired_orders` list against the current `open_orders`
dict. Returns an `ActionPlan(to_cancel, to_place, skipped_cancels, skipped_places)`.
Pure function — no side effects; the caller drives execution.

**Key controls:**
- `min_order_lifetime_seconds` (default 5s): orders younger than this are not cancelled.
- `max_cancels_per_minute` / `max_places_per_minute` (default 10 each): sliding 60s window.
- Excess actions are skipped and counted in `ActionPlan.skipped_*`.

## How to run in replay

```bash
python -m polytool simtrader run \
  --tape artifacts/simtrader/tapes/<run_id>/events.jsonl \
  --strategy market_maker_v0 \
  --strategy-config-json '{"tick_size": "0.01", "order_size": "10"}'
```

## How to run in shadow mode

```bash
python -m polytool simtrader shadow \
  --market <slug> \
  --strategy market_maker_v0 \
  --duration 300
```

`ShadowRunner` streams live WS events; `MarketMakerV0` responds via the
standard `Strategy` interface — no extra wiring required.

## How to run in dry-run live mode

```bash
python -m polytool simtrader live \
  --strategy market_maker_v0 \
  --best-bid 0.45 \
  --best-ask 0.55 \
  --asset-id <token_id>
```

Optional overrides:

```bash
python -m polytool simtrader live \
  --strategy market_maker_v0 \
  --best-bid 0.45 --best-ask 0.55 \
  --asset-id <token_id> \
  --inventory-units 5 \
  --mm-tick-size 0.01 \
  --mm-order-size 10 \
  --kill-switch artifacts/kill_switch.txt \
  --rate-limit 30 \
  --max-order-notional 25 \
  --max-position-notional 100 \
  --daily-loss-cap 15
```

In dry-run mode (default):
- Prints `WOULD PLACE BUY/SELL <price> <size>` lines to stderr per quote.
- Runs `OrderManager.reconcile_once()` against empty open_orders (one-shot tick).
- Passes quotes through `LiveRunner.run_once()` → `RiskManager` → `LiveExecutor` (no client call).
- Prints a JSON summary to stdout.

## Safety properties

| Property | Guarantee |
|----------|-----------|
| **Dry-run default** | No orders submitted unless `--live` is explicitly passed |
| **Kill switch first** | Checked before every place/cancel action, even in dry-run |
| **No market orders** | Limit orders only; no taker aggressors |
| **Binary bounds** | Bid `> 0`, ask `< 1` enforced by MarketMakerV0 guards |
| **Churn limits** | Min-lifetime and per-minute rate caps enforced by OrderManager |
| **Risk caps** | Order, position, daily-loss, and inventory notional limits via RiskManager |

## Current boundary / open questions

1. **OrderManager ↔ LiveExecutor**: `to_cancel` from `ActionPlan` is not yet
   wired to `executor.cancel_order` in the one-shot CLI path (empty open_orders,
   so this is inert at Stage 0).
2. **Inventory persistence**: `MarketMakerV0._inventory` resets on `on_start`;
   for `simtrader live` (fresh strategy per invocation), supply `--inventory-units`
   from external state. A persistent state file is needed for multi-tick operation.
3. **Tick size discovery**: operator must supply `--mm-tick-size`; auto-detection
   from `tick_size_change` events is not yet implemented.

## References

- `docs/specs/SPEC-0011-live-execution-layer.md`
- `docs/features/FEATURE-trackA-week1-execution-primitives.md`
- `docs/dev_logs/2026-03-05_trackA_week2_market_maker_v0.md`
