# SimTrader Sports Strategies v1 (PMXT Deliverable B)

**Status:** Shipped 2026-04-22  
**Track:** 1C (Sports Directional)  
**Commit:** `efb6f01 feat(simtrader): PMXT Deliverable B -- merge-ready sports strategies`

---

## What Shipped

Three sports-specific strategy classes for SimTrader, wired into `STRATEGY_REGISTRY`,
with a 20-test offline suite. All three are replay-ready; live/shadow deployment requires
the deferred hardening items listed below.

| Strategy | Class | Registry Key | Signal |
|---|---|---|---|
| Final Period Momentum | `SportsMomentum` | `sports_momentum` | Below-to-above midpoint crossing in final window |
| Late Favorite Limit Hold | `SportsFavorite` | `sports_favorite` | Midpoint at-or-above threshold within activation window |
| VWAP Reversion | `SportsVWAP` | `sports_vwap` | Price below rolling VWAP; exit on reversion or limit |

---

## Files

| File | Role |
|---|---|
| `packages/polymarket/simtrader/strategies/sports_momentum.py` | SportsMomentum implementation |
| `packages/polymarket/simtrader/strategies/sports_favorite.py` | SportsFavorite implementation |
| `packages/polymarket/simtrader/strategies/sports_vwap.py` | SportsVWAP implementation |
| `packages/polymarket/simtrader/strategy/facade.py` | STRATEGY_REGISTRY entries for all three |
| `tests/test_sports_strategies.py` | 20-test offline suite |

---

## Strategy Details

### SportsMomentum

**Entry:** Midpoint crosses from below `entry_price` (default 0.80) while `ts_recv` is
inside the window `[market_close_time - final_period_minutes * 60, market_close_time]`.
No crossing required on the first tick — only a below-to-above transition triggers BUY.
If `market_close_time <= 0`, strategy is disabled entirely.

**Exit:** First of: `price >= take_profit_price` (default 0.92),
`price <= stop_loss_price` (default 0.50), or `ts_recv >= market_close_time`. All exits
use `reason="momentum_exit"`. One entry per tape.

**Config keys:**

| Key | Type | Default | Note |
|---|---|---|---|
| `market_close_time_ns` | float | 0.0 | Unix nanoseconds; takes priority when > 0 |
| `market_close_time` | float | 0.0 | Unix seconds fallback |
| `final_period_minutes` | float | 30.0 | Window width |
| `entry_price` | float | 0.80 | Crossing threshold |
| `take_profit_price` | float | 0.92 | Exit above |
| `stop_loss_price` | float | 0.50 | Exit below |
| `trade_size` | int | 100 | Shares per order |

---

### SportsFavorite

**Entry:** Single BUY when `midpoint >= entry_price` (default 0.90) and `ts_recv` is
inside `[activation_start_time, market_close_time]`. No crossing required — any tick
at-or-above the threshold fires BUY. If `activation_start_time <= 0`, activates
immediately. If `market_close_time <= 0`, no upper-bound cutoff.

**Exit:** None. Position is held open through tape end (runner marks to settlement).
Downstream PnL tool must handle open positions at tape end.

**Config keys:**

| Key | Type | Default | Note |
|---|---|---|---|
| `activation_start_time_ns` | float | 0.0 | Unix nanoseconds; takes priority when > 0 |
| `activation_start_time` | float | 0.0 | Unix seconds fallback |
| `market_close_time_ns` | float | 0.0 | Unix nanoseconds; takes priority when > 0 |
| `market_close_time` | float | 0.0 | Unix seconds fallback |
| `entry_price` | float | 0.90 | Threshold |
| `trade_size` | int | 25 | Shares per order |

---

### SportsVWAP

**Accumulation:** Absorbs `last_trade_price` events into a rolling `deque(maxlen=vwap_window)`.
Ticks with `trade_size < min_tick_size` are filtered out. Becomes eligible only after
`vwap_window` (default 80) qualifying observations with positive total size.

**Entry:** `price < vwap - entry_threshold` (default 0.008) once window is full, with
`best_ask` available. `reason="vwap_entry"`.

**Exit priority:**
1. `price >= fill + take_profit` → `reason="vwap_take_profit"`
2. `price <= fill - stop_loss` → `reason="vwap_stop_loss"`
3. `price >= vwap - exit_threshold` → `reason="vwap_reversion"`

**Config keys:**

| Key | Type | Default | Note |
|---|---|---|---|
| `vwap_window` | int | 80 | Rolling window size |
| `entry_threshold` | float | 0.008 | Entry gap below VWAP |
| `exit_threshold` | float | 0.002 | Reversion gap above VWAP |
| `min_tick_size` | float | 0.0 | Minimum accepted trade size (filters on size, not price) |
| `take_profit` | float | 0.015 | Absolute offset above fill |
| `stop_loss` | float | 0.02 | Absolute offset below fill |
| `trade_size` | int | 1 | Shares per order |

---

## `_ns` Config Key Priority Rule

Both `SportsMomentum` and `SportsFavorite` apply the same priority rule:

```python
effective = ns_value / 1e9 if ns_value > 0 else seconds_value
```

Passing `*_ns=0` leaves the seconds-based param in effect. This is resolved once at
constructor time; all internal comparisons use Unix seconds to match `ts_recv`.

This matters for `--strategy-config-json`: Polymarket tape `ts_recv` values are Unix
seconds, so nanosecond config values like `market_close_time_ns=120000000000` represent
120 seconds (2 minutes from epoch), not a real wall-clock time. Operators must verify
the nanosecond value represents the intended Unix epoch nanosecond, not a duration.

---

## Attribution and License

Signal logic and default parameters are derived from behavioral research in
`evan-kolberg/prediction-market-backtesting`. That repository's strategy files are
LGPL-covered (per its `NOTICE` file). The PolyTool implementations are clean-room
reimplementations: no structural or expression copying, only parameter and behavioral
research reuse.

---

## Test Coverage

**20 tests** in `tests/test_sports_strategies.py`.

| Scenario | Test |
|---|---|
| M1 — momentum entry + take profit | `test_sports_momentum_entry_and_take_profit` |
| M1 — stop loss exit | `test_sports_momentum_stop_loss_exit` |
| M2 — already above threshold, no entry | `test_sports_momentum_already_above_threshold_no_entry` |
| M3 — close time exit via ns param | `test_sports_momentum_close_time_exit` |
| M4 — disabled when close_time=0 | `test_sports_momentum_disabled_when_close_time_zero` |
| F1 — entry on signal | `test_sports_favorite_entry_on_signal` |
| F2 — before activation, then entry | `test_sports_favorite_before_activation_then_entry` |
| F3 — post-close signal ignored | `test_sports_favorite_post_close_ignored` |
| F4 — no exit after fill | `test_sports_favorite_no_exit_after_fill` |
| V1 — min_tick_size filters small trades | `test_sports_vwap_min_tick_size_filters_small_trades` |
| V2 — entry and reversion exit | `test_sports_vwap_entry_and_reversion_exit` |
| V3 — take profit exit | `test_sports_vwap_take_profit_exit` |
| V4 — stop loss exit | `test_sports_vwap_stop_loss_exit` |
| Size-weighted VWAP proof | `test_sports_vwap_size_weighted_vwap` |
| Registry: ns config keys accepted | `test_ns_config_keys_accepted` |
| ... (5 additional parametric/edge cases) | |

**Regression:** 186 existing tests (simtrader strategy, portfolio, market_maker_v1)
passing with no regressions.

---

## Validation Ladder Status

| Level | Status |
|---|---|
| L0 — unit tests (offline, deterministic) | PASS — 20/20 |
| L1 — multi-tape replay | NOT YET — deferred (see below) |
| L2 — scenario sweep | NOT YET |
| L3 / Gate 3 — live shadow | NOT YET |

---

## Deferred Hardening (not blocking for Deliverable B)

1. **Position-size guard** — No max-position check exists in the strategy layer. Required
   before live or shadow use to prevent runaway sizing on stale signals.

2. **`SportsFavorite` open-position PnL handling** — Strategy holds positions open at tape
   end. The downstream PnL tool and ledger must be verified to handle this case correctly
   before results from `SportsFavorite` runs are treated as meaningful.

3. **Gold tape for VWAP validation** — The 80-tick VWAP window requires a tape with
   sufficient `last_trade_price` density. Silver tapes typically lack this. VWAP replay
   results are only meaningful against Gold-tier tapes.

4. **`*_ns` precedence test** — Optional: add one test per strategy proving that when
   both `market_close_time_ns > 0` and `market_close_time > 0` are provided with
   conflicting values, the `_ns` field wins.

5. **Track 1C activation decision** — These strategies are fully implemented but Track 1C
   (sports directional model) activation depends on a Director decision. See
   `docs/CURRENT_DEVELOPMENT.md` Awaiting Decision section.

---

## Codex Review Summary

- Tier: Recommended (strategy files)
- Issues found across all review passes: 4 (3 blocking, 1 non-blocking exit-reason gap)
- Issues addressed: all 4 addressed in fix pass `2026-04-22_deliverable-b_fix-pass.md`
- Re-review verdict: MERGE-READY (`2026-04-22_deliverable-b_rereview.md`)

---

## Related Dev Logs

| Log | Date | Content |
|---|---|---|
| [Deliverable B — Context Fetch](../dev_logs/2026-04-21_deliverable-b_context-fetch.md) | 2026-04-21 | Upstream context fetch, work packet definition |
| [Deliverable B — Reference Extract](../dev_logs/2026-04-21_deliverable-b_reference-extract.md) | 2026-04-21 | Clean-room license analysis, parameter extraction |
| [Deliverable B — Implementation](../dev_logs/2026-04-21_deliverable-b_impl.md) | 2026-04-21 | Initial implementation of all three strategies |
| [Deliverable B — Validation Pack](../dev_logs/2026-04-22_deliverable-b_validation-pack.md) | 2026-04-22 | M1-M4, F1-F4, V1-V4 scenario definitions |
| [Deliverable B — Fix Pass](../dev_logs/2026-04-22_deliverable-b_fix-pass.md) | 2026-04-22 | 4 blockers fixed, 11 new tests, 4 tightened |
| [Deliverable B — Re-review](../dev_logs/2026-04-22_deliverable-b_rereview.md) | 2026-04-22 | MERGE-READY re-verification |
| [Deliverable B — Close-out](../dev_logs/2026-04-22_deliverable-b_closeout.md) | 2026-04-22 | Docs close-out: feature doc, INDEX, CURRENT_DEVELOPMENT |
