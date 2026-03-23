# MarketMakerV1 Calibration Plumbing

**Date:** 2026-03-10
**Branch:** codex/tracka-adverse-selection-default-wiring
**Scope:** MarketMakerV1 calibration only — no changes to V0, session-pack, adverse-selection math, or scanner logic.

---

## What Changed

### 1. `sigma_b` — Realized logit-mid variance (pre-existing, now tested)

`_record_mid` in V1 already stored `logit(clip(mid))` rather than raw mid, and `_sigma_sq` already computed rolling population variance of logit-mid first-differences.  No logic was changed; tests were added to verify:

- Returns `_DEFAULT_SIGMA_SQ_LOGIT = 0.003` when fewer than 3 history points exist.
- Returns computed variance (different from default) when 3+ points exist.
- Higher-variance price paths produce higher sigma values.
- Entries outside `vol_window_seconds` are pruned correctly.
- History is stored as logit values, not raw probabilities.

### 2. `kappa` — Trade-arrival proxy with explicit static fallback (new)

**What kappa calibration is truly using today:**

> The calibrated kappa is the `last_trade_price` event arrival rate observed in the rolling `vol_window_seconds` window, linearly scaled by `_KAPPA_TRADES_PER_SEC_SCALE = 10.0`.  This is an **ordinal proxy** — not an MLE estimate of the A-S fill-decay parameter κ.

**Why MLE is not available:**
True MLE calibration of κ requires observing fill rates at multiple posted spread levels over many sessions.  That data is not available during a single tape replay.  The fill-decay parameter κ describes how quickly fill probability drops as we post further from the midpoint — a quantity that cannot be estimated from order-book snapshots or trade timestamps alone.

**What the proxy measures correctly:**
A busier market (more `last_trade_price` events) is more liquid and supports a tighter spread.  This ordinal direction is correct.  The absolute scale is anchored by the clamp `[_MIN_KAPPA=0.20, _MAX_KAPPA=10.0]`, which keeps the A-S spread formula in the same regime as the constructor default (`kappa=1.50`).

**Explicit fallback:**
When fewer than `_MIN_TRADES_FOR_KAPPA = 5` trade arrivals are present in the rolling window, `_kappa()` returns `self.mm_config.kappa` verbatim.  This is logged as a code-path decision, not a silent guess.

**Proxy formula:**
```
rate  = n_trades / vol_window_seconds       # trades/second
kappa = clamp(rate × 10.0, 0.20, 10.0)
```

At 1 trade per 10 seconds (rate = 0.1 t/s) this yields kappa ≈ 1.0, matching the constructor default for a moderately active market.

### 3. Wiring in `_compute_quotes`

The logit-space spread formula previously read `self.mm_config.kappa` directly.  It now calls `self._kappa(self._last_ts_recv or 0.0)`, which returns either the live proxy or the static fallback transparently.

### 4. `on_event` override

V1 now overrides `on_event` to call `_record_trade_arrival(event, ts_recv)` before forwarding to `super().on_event(...)`.  Only `last_trade_price` events are counted; all other event types are ignored.

### 5. Lifecycle (`__init__` + `on_start`)

- `__init__(*args, **kwargs)` initializes `_trade_arrival_ts: deque[float]` before any event can arrive.
- `on_start` calls `super().on_start(...)` then clears `_trade_arrival_ts`, ensuring a clean state between sessions.

---

## Files Changed

| File | Change |
|------|--------|
| `packages/polymarket/simtrader/strategies/market_maker_v1.py` | Add `_MIN_TRADES_FOR_KAPPA`, `_KAPPA_TRADES_PER_SEC_SCALE`, `_MIN_KAPPA`, `_MAX_KAPPA`; add `__init__`, `on_start`, `_record_trade_arrival`, `_kappa`, `on_event` overrides; update `_compute_quotes` to call `_kappa()` |
| `tests/test_market_maker_v1.py` | New file: 30 tests covering sigma_b, kappa calibration/fallback, quote bounds, and V0 regression guard |
| `docs/dev_logs/2026-03-10_marketmaker_v1_calibration_plumbing.md` | This file |

---

## Tests Run

```
tests/test_market_maker_v1.py   30 passed
tests/test_market_maker_v0.py   30 passed
```

---

## Manual Verification Commands

```bash
# All new V1 tests
python -m pytest tests/test_market_maker_v1.py -v --tb=short

# V0 regression check
python -m pytest tests/test_market_maker_v0.py -v --tb=short

# Spot-check: kappa proxy with simulated trade arrivals
python - <<'EOF'
from packages.polymarket.simtrader.strategies.market_maker_v1 import MarketMakerV1
mm = MarketMakerV1(kappa=1.5, vol_window_seconds=60.0)
print("no trades (fallback):", mm._kappa(1000.0))  # expect 1.5

for i in range(10):
    mm._record_trade_arrival({"event_type": "last_trade_price"}, 960.0 + i)
print("10 trades in 60s:", mm._kappa(999.0))  # expect clamp(10/60*10, 0.2, 10.0) ≈ 1.667
EOF
```

---

## What Is NOT Calibrated

- **κ (fill-decay rate)**: The A-S κ controls how fill probability decays with posted spread.  This requires fill observations at multiple spread levels — not available from the current tape.  The trade-arrival proxy is ordinal-correct but not in the same units.
- **γ (risk aversion)**: Static constructor parameter.  No data path to calibrate it from current inputs.
- **σ² absolute scale**: The logit-space variance is computed correctly from realized mid changes, but the `vol_window_seconds` window size and minimum sample threshold are hyperparameters set by the operator.

These gaps are deferred to a future calibration pass that requires multi-session fill data.
