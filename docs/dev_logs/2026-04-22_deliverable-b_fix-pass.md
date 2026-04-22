# 2026-04-22 PMXT Deliverable B — Fix Pass

## Objective

Address all blocking and non-blocking issues identified in the adversarial review
(`2026-04-22_deliverable-b_adversarial_review.md`) and audit
(`2026-04-22_deliverable-b_audit.md`). Deliver merge-ready sports strategies.

---

## Files Changed

| File | Change |
|------|--------|
| `packages/polymarket/simtrader/strategies/sports_momentum.py` | Add `market_close_time_ns` param; fix attribution |
| `packages/polymarket/simtrader/strategies/sports_favorite.py` | Add `activation_start_time_ns` and `market_close_time_ns` params; fix attribution |
| `packages/polymarket/simtrader/strategies/sports_vwap.py` | Fix `min_tick_size` filter (size not price); differentiate exit reasons; fix attribution |
| `tests/test_sports_strategies.py` | Add 11 tests; tighten 4 existing assertion counts |

---

## Fixes Applied

### 1. `*_ns` config key support (momentum + favorite)

Both strategies now accept the nanosecond config keys documented in the validation pack
and used by `--strategy-config-json`:

- `SportsMomentum`: added `market_close_time_ns: float = 0.0`. When `> 0`, divides by
  `1e9` and uses as `market_close_time`. Seconds-based `market_close_time` remains as
  fallback (backward compatible).
- `SportsFavorite`: added `activation_start_time_ns: float = 0.0` and
  `market_close_time_ns: float = 0.0` with same `_ns > 0` priority logic.

The `*_ns > 0` guard is explicit: passing `market_close_time_ns=0` leaves the
seconds-based param in effect. No ambiguity.

Verified via `_build_strategy("sports_momentum", {"market_close_time_ns": 120e9})` —
no longer raises `StrategyRunConfigError`.

### 2. `min_tick_size` filter corrected (VWAP)

Old code: `if tick_price > cfg.min_tick_size` — compared trade price against size threshold.

Fixed code: extract `tick_size` first, then `if tick_size >= cfg.min_tick_size` —
filters ticks with trade size below the minimum.

With default `min_tick_size=0.0`, all non-negative sizes pass (no behavior change for
existing tests). With `min_tick_size=50`, only trades with size >= 50 accumulate into
the VWAP window — consistent with the validation pack V1 definition.

### 3. VWAP exit reasons differentiated

Old code: all exits used `reason="vwap_exit"`.

Fixed: `reason` now reflects the specific branch:
- `"vwap_take_profit"` — `price >= fill + take_profit`
- `"vwap_stop_loss"` — `price <= fill - stop_loss`
- `"vwap_reversion"` — VWAP reversion condition

### 4. Attribution corrected

Old text: `"...derived from ... evan-kolberg/prediction-market-backtesting (MIT License)."`

Fixed: `"...derived from sports strategy research in evan-kolberg/prediction-market-backtesting."`

The upstream repository is mixed-license (LGPL for those specific strategy files per
the reference extract). The "(MIT License)" claim was factually incorrect. The new
text credits the behavioral/parameter research without misrepresenting the upstream
license.

---

## Tests Added (11 new)

| Test | V-Pack Scenario | What it covers |
|------|-----------------|----------------|
| `test_sports_momentum_already_above_threshold_no_entry` | M2 | First tick above threshold does not enter; only crossing-from-below triggers BUY |
| `test_sports_momentum_close_time_exit` | M3 | SELL fires at `ts_recv >= market_close_time_ns/1e9`; uses ns param |
| `test_sports_momentum_disabled_when_close_time_zero` | M4 | `market_close_time_ns=0` disables strategy entirely |
| `test_sports_favorite_before_activation_then_entry` | F2 | Signal before `activation_start_time_ns` ignored; first eligible tick fires BUY |
| `test_sports_favorite_post_close_ignored` | F3 | Signal after `market_close_time_ns` ignored |
| `test_sports_favorite_no_exit_after_fill` | F4 | No SELL emitted after fill; position held open |
| `test_sports_vwap_min_tick_size_filters_small_trades` | V1 | Sizes 10/20 filtered; sizes 100 accumulate; window fills only with accepted ticks |
| `test_sports_vwap_take_profit_exit` | V3 | Exit `reason="vwap_take_profit"` when fill+take_profit reached |
| `test_sports_vwap_stop_loss_exit` | V4 | Exit `reason="vwap_stop_loss"` when fill-stop_loss reached |
| `test_sports_vwap_size_weighted_vwap` | (implicit) | Trades (0.90×1000, 0.90×1000, 0.82×1): weighted VWAP triggers entry at 0.82; equal-weight would not |
| `test_ns_config_keys_accepted` | (registry) | `_build_strategy` accepts `market_close_time_ns` and `activation_start_time_ns` without raising; verifies converted seconds values |

## Tests Tightened (4 existing)

- `test_sports_momentum_entry_and_take_profit`: now asserts `len(decisions) == 2`
- `test_sports_momentum_stop_loss_exit`: now asserts `len(decisions) == 2`
- `test_sports_favorite_entry_on_signal`: now asserts `len(decisions) == 1`
- `test_sports_vwap_entry_and_reversion_exit`: now asserts `len(decisions) == 2`

---

## Test Results

```
tests/test_sports_strategies.py ....................   20 passed in 0.73s
```

Regression suites:

```
tests/test_simtrader_strategy.py + test_simtrader_portfolio.py + test_market_maker_v1.py
186 passed in 1.70s
```

CLI smoke: `python -m polytool --help` — exit 0.

---

## Open Questions Carried Forward

- Position-size guard for sports strategies before live/shadow use.
- `SportsFavorite` open positions at tape end — downstream PnL tool handling.
- Gold tape requirement for meaningful VWAP validation (80-tick window).
- Validation pack JSON examples still use `market_close_time_ns` in seconds notation
  (e.g. `120000000000`) while `ts_recv` is Unix seconds — no code change needed but
  operators should be aware of the unit difference when writing config JSON.

---

## Codex Review Summary

- Tier: Recommended (strategy files)
- Issues found: 4 (3 blocking from adversarial review + 1 non-blocking exit-reason gap)
- Issues addressed: all 4 in this pass
