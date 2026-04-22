# 2026-04-21 PMXT Deliverable B — Sports Strategy Foundations Implementation

## Objective

Implement `sports_momentum`, `sports_favorite`, and `sports_vwap` strategies for SimTrader.
Register them in `STRATEGY_REGISTRY`. Write synthetic-tape tests. Clean-room only — behavior
and parameter tables sourced from the reference-extract dev log; no upstream code copied.

---

## Files Changed

| File | Change |
|------|--------|
| `packages/polymarket/simtrader/strategies/sports_momentum.py` | Created |
| `packages/polymarket/simtrader/strategies/sports_favorite.py` | Created |
| `packages/polymarket/simtrader/strategies/sports_vwap.py` | Created |
| `packages/polymarket/simtrader/strategy/facade.py` | 3 registry entries added |
| `tests/test_sports_strategies.py` | Created |

---

## Strategy Summaries

### SportsMomentum (`sports_momentum`)

- Activates inside `[market_close_time - final_period_minutes*60, market_close_time]`.
- If `market_close_time <= 0` strategy never activates.
- Entry: midpoint crosses below→above `entry_price` within the window.
- Exit: `take_profit_price`, `stop_loss_price`, or `at_close`.
- One entry per tape. State: `_prev_price`, `_entry_pending`, `_fill_price`, `_done`.
- Config: `MomentumConfig` frozen dataclass. Defaults: entry=0.80, take_profit=0.92, stop_loss=0.50, trade_size=100.

### SportsFavorite (`sports_favorite`)

- Optional activation window: `[activation_start_time, market_close_time]`.
  `<= 0` values disable the respective bound.
- Entry: midpoint >= `entry_price` and `best_ask` is available.
- No in-strategy exit — position held open for runner/settlement marking.
- One entry per tape. State: `_entered`.
- Config: `FavoriteConfig` frozen dataclass. Defaults: entry=0.90, trade_size=25.

### SportsVWAP (`sports_vwap`)

- Accumulates `last_trade_price` events into a rolling `deque(maxlen=vwap_window)` of
  `(price, size)` tuples. `size` defaults to 1.0 if absent in the event.
- Becomes eligible only after exactly `vwap_window` ticks with positive total size.
- Ticks with `price <= min_tick_size` are skipped.
- Entry: `current_price < vwap - entry_threshold` and `best_ask` is available.
- Exit priority: take_profit absolute offset → stop_loss absolute offset → VWAP reversion
  (`current_price >= vwap - exit_threshold`).
- One entry per tape. State: `_window`, `_last_price`, `_entry_pending`, `_fill_price`, `_done`.
- Config: `VWAPConfig` frozen dataclass. Defaults: vwap_window=80, entry_threshold=0.008,
  exit_threshold=0.002, take_profit=0.015, stop_loss=0.02, trade_size=1.

---

## Design Decisions

- **Frozen dataclass configs** — Pydantic is not installed; frozen `@dataclass` matches the
  `MMConfig` pattern in `market_maker_v0.py`.
- **Constructor params = strategy_config JSON keys** — registry passes kwargs verbatim;
  `market_close_time`, `activation_start_time`, etc. must be in the config JSON.
- **Signal price is midpoint** — consistent with the reference "quote variant" behavior.
  Order prices: BUY at `best_ask`, SELL at `best_bid` (or `fill_price` fallback).
- **One-shot per tape** — all three strategies exit to `_done=True` after the full BUY/SELL
  cycle. Re-entry not supported in v1.
- **VWAP size default=1.0** — `last_trade_price` events may not carry a `size` field; degenerate
  to equal-weight average rather than raising.
- **No shared indicator module** — VWAP window uses inline `deque(maxlen=N)`, consistent with
  `MarketMakerV1._mid_history`.

---

## Test Results

```
tests/test_sports_strategies.py .........  9 passed in 0.40s
```

Full regression suite: 4144 passed, 8 pre-existing failures
(all in `test_ris_phase2_cloud_provider_routing.py`, unrelated to this work).

Tests written (9 total):
- `test_sports_momentum_entry_and_take_profit` — crossing in window + take_profit exit
- `test_sports_momentum_no_entry_outside_window` — no signal when ts_recv outside window
- `test_sports_momentum_stop_loss_exit` — stop_loss triggers SELL
- `test_sports_favorite_entry_on_signal` — midpoint >= entry_price → BUY
- `test_sports_favorite_no_entry_before_activation` — activation_start_time blocks entry
- `test_sports_favorite_one_entry_only` — signal fires every tick but only one BUY
- `test_sports_vwap_entry_and_reversion_exit` — window fills → entry → VWAP reversion exit
- `test_sports_vwap_no_entry_insufficient_window` — fewer than vwap_window trades → no entry
- `test_strategy_registry_contains_all_three` — all 3 names registered; instantiation via `_build_strategy`

---

## CLI Verification

```
python -c "from packages.polymarket.simtrader.strategy.facade import known_strategies; print(known_strategies())"
# → ['binary_complement_arb', 'copy_wallet_replay', 'market_maker_v0', 'market_maker_v1',
#    'sports_favorite', 'sports_momentum', 'sports_vwap']
```

CLI route: `python -m polytool simtrader run --tape <PATH> --strategy sports_momentum --strategy-config-json '{"market_close_time":1745280000.0}'`

---

## Attribution

All three strategies carry the attribution comment:

> Signal logic and default parameters derived from sports strategy research in
> evan-kolberg/prediction-market-backtesting (MIT License).
> Reimplemented from scratch for PolyTool SimTrader.

Reference extract log: `docs/dev_logs/2026-04-21_deliverable-b_reference-extract.md`

---

## Open Questions

- Upstream `vwap_reversion` uses `trade_size=1` as a quantity (not dollar notional);
  no affordability cap is applied at the SimTrader level for sports strategies. Confirm
  whether a position-size guard should be added before live/shadow use.
- `sports_favorite` intentionally holds open — confirm downstream tools handle
  open positions correctly when calculating final PnL on tape end.
- Gold tapes required for meaningful VWAP validation (80-tick window); Silver tapes
  (~2-min resolution) unlikely to provide enough `last_trade_price` events.

---

## Codex Review

Tier: Recommended (strategy file). Review deferred — no execution-layer code touched,
no kill-switch or risk-manager paths modified. Schedule before first shadow run.
