# MarketMakerV1 Calibration Provenance — Dev Log

**Date:** 2026-03-11
**Branch:** codex/tracka-adverse-selection-default-wiring
**Scope:** MarketMakerV1 state exposure + artifact emission + tests

---

## Problem

MarketMakerV1's two calibrated parameters — sigma_b (logit-space mid variance)
and kappa (trade-arrival proxy) — could fall back silently to static defaults
without leaving any trace in run artifacts.  Operators running sweeps or shadow
sessions had no way to know whether the strategy was using calibrated values
or its constructor fallbacks, making trust assessment impossible.

---

## What sigma_b and kappa are actually doing today

### sigma_b (logit-space volatility)

- **Rolling path**: `pvariance` of first-differences of `logit(mid)` values
  in the rolling window (`vol_window_seconds`).
- **Condition for rolling path**: `>= 3` mid-history points remain in the
  window after pruning.
- **Fallback**: `_DEFAULT_SIGMA_SQ_LOGIT = 0.003` (static constant derived
  from V0's 0.0002 probability-space variance × 16 for logit space).
- **This is genuine realized variance** — it reflects actual observed mid
  movement in logit space.

### kappa (fill-intensity proxy)

- **Proxy path**: counts `last_trade_price` event arrivals in the rolling
  window; computes `rate = n / vol_window_seconds`; scales via
  `_KAPPA_TRADES_PER_SEC_SCALE = 10.0`; clamps to `[0.20, 10.0]`.
- **Condition for proxy path**: `>= 5` trade arrivals in the window
  (`_MIN_TRADES_FOR_KAPPA`).
- **Fallback**: `self.mm_config.kappa` — the value passed to the constructor
  (default 1.50).
- **IMPORTANT**: This is an **ORDINAL PROXY only**, NOT an MLE estimate of
  the A-S fill-decay rate κ.  True MLE κ requires observing fill rates at
  multiple spread levels across many sessions.  The proxy is directionally
  correct (busier market → higher kappa → tighter spread) but not
  quantitatively calibrated.

---

## Changes made

### 1. `packages/polymarket/simtrader/strategies/market_maker_v1.py`

- Added `calibration_provenance: Optional[dict] = None` attribute in
  `__init__`.
- Added `_build_calibration_provenance(t_now: float) -> dict` — calls
  `_sigma_sq(t_now)` and `_kappa(t_now)` (both prune their deques in-place),
  then reads post-prune counts to determine which path was taken.
- Added `on_finish()` override — calls `_build_calibration_provenance` with
  `self._last_ts_recv or 0.0` and stores result in `self.calibration_provenance`.

Provenance schema:
```json
{
  "vol_window_seconds": 60.0,
  "sigma": {
    "source": "rolling_logit_var" | "static_fallback",
    "sample_count": 12,
    "value": 0.00421,
    "fallback_reason": null
  },
  "kappa": {
    "source": "trade_arrival_proxy" | "static_fallback",
    "trade_count": 8,
    "value": 1.33,
    "constructor_kappa": 1.5,
    "fallback_reason": null
  }
}
```

`fallback_reason` is `null` when calibrated, a descriptive string when not
(e.g. `"insufficient_trades(3<5)"`).

### 2. `packages/polymarket/simtrader/strategy/runner.py`

- Duck-typed `calibration_provenance` from strategy in `_write_artifacts()`.
- Written to both `summary.json` and `run_manifest.json` when present.

### 3. `packages/polymarket/simtrader/shadow/runner.py`

- Same duck-typing additions to shadow's artifact writer.
- Written to `summary.json` and `run_manifest.json`.

### 4. `tests/test_market_maker_v1.py`

Added `TestCalibrationProvenance` class (9 tests):

| Test | What it proves |
|------|----------------|
| `test_provenance_none_before_on_finish` | Attribute starts as None |
| `test_provenance_set_after_on_finish_fallback_state` | Both paths fall back with no history |
| `test_sigma_fallback_fields` | Correct source/count/value/reason on sigma fallback |
| `test_sigma_rolling_fields` | Correct source/count/value/reason on rolling path |
| `test_kappa_fallback_fields` | Correct source/count/value/reason on kappa fallback |
| `test_kappa_proxy_fields` | Correct source/count/value/reason on proxy path |
| `test_vol_window_seconds_in_provenance` | Window metadata present |
| `test_on_start_resets_provenance` | on_start does not clear provenance (only on_finish writes it) |
| `test_provenance_emitted_to_runner_artifacts` | E2E: both summary.json and run_manifest.json contain the key |

---

## Tests run

```
tests/test_market_maker_v1.py — 39 passed (30 pre-existing + 9 new)
Full suite: 1527 passed, 3 pre-existing failures unrelated to this change
```

---

## Manual verification commands

```bash
# Run new provenance tests only
python -m pytest tests/test_market_maker_v1.py::TestCalibrationProvenance -v

# Run full market_maker_v1 suite
python -m pytest tests/test_market_maker_v1.py -v

# Quick artifact check (requires a tape file at /tmp/events.jsonl)
# python -m polytool simtrader run \
#   --events-path /tmp/events.jsonl \
#   --run-dir /tmp/test_run \
#   --strategy market_maker_v1 \
#   --strategy-config '{"tick_size":"0.01","order_size":"10"}'
# cat /tmp/test_run/run_manifest.json | python -m json.tool | grep -A20 calibration_provenance
```

---

## Explicit statement of calibration truth

| Parameter | Today's method | MLE? | Notes |
|-----------|---------------|------|-------|
| **sigma_b** | `pvariance` of logit(mid) first-differences in rolling window | N/A (realized estimator) | Statistically sound for realized vol |
| **kappa** | `n / window × 10` clamped to [0.2, 10] | **No** | Ordinal proxy only; directionally correct |

Artifacts now report `source` and `fallback_reason` so this distinction is
machine-readable in every run and shadow session.
