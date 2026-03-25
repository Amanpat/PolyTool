# Dev Log: Phase 1A Accumulation Engine v0

**Date**: 2026-03-22
**Branch**: phase-1A
**Scope**: Track 2 / Phase 1A — crypto pair bot core engine
**Author**: Claude Code

---

## Objective

Implement the three core engine modules for the Phase 1A crypto pair bot and provide full offline test coverage. No CLI wiring, no network calls in tests, no live-execution layer touched.

---

## Deliverables

### New modules

| Module | Purpose |
|---|---|
| `packages/polymarket/crypto_pairs/reference_feed.py` | Binance WebSocket reference price feed with explicit connection/stale state |
| `packages/polymarket/crypto_pairs/fair_value.py` | Log-normal fair value estimator for 5m/15m binary crypto markets |
| `packages/polymarket/crypto_pairs/accumulation_engine.py` | Deterministic 4-gate accumulation engine (pure function, no side-effects) |

### New tests

| Test file | Tests |
|---|---|
| `tests/test_crypto_pair_reference_feed.py` | 29 |
| `tests/test_crypto_pair_fair_value.py` | 45 |
| `tests/test_crypto_pair_accumulation_engine.py` | 37 |
| **Total** | **111** |

---

## Design Decisions

### reference_feed.py

- `FeedConnectionState(str, Enum)` with values `NEVER_CONNECTED`, `CONNECTED`, `DISCONNECTED` — first-class connection lifecycle, not a boolean.
- `ReferencePriceSnapshot` is a frozen dataclass (immutable, thread-safe to share across callers). `is_usable` is a property computed from the three independent conditions: price present, not stale, and CONNECTED.
- Stale condition: `age_s > stale_threshold_s` (strictly greater than). A price observed exactly at the threshold boundary is not yet stale.
- `_inject_price()` is the offline/test hook. It bypasses the WebSocket entirely and immediately sets state to CONNECTED so `is_usable` returns True.
- `_time_fn` is injectable (default `time.time`) so tests can advance time without real delays.
- `connect()` starts a daemon thread; tests never call `connect()`. The WS loop reconnects with 2s backoff. Coinbase fallback is not implemented but `feed_source` field reserves space for it.
- Supported symbols: `BTC`, `ETH`, `SOL` only. Case-insensitive inputs normalized to upper.
- Binance combined aggTrade stream URL baked in: `wss://stream.binance.com:9443/stream?streams=btcusdt@aggTrade/ethusdt@aggTrade/solusdt@aggTrade`

### fair_value.py

- Model: log-normal no-drift (risk-neutral approximation). `d = ln(S/K) / (σ·√τ)`, `P(YES) = N(d)`, `P(NO) = 1 − N(d)`.
- Standard normal CDF via `math.erf` from stdlib — no scipy dependency.
- Default annual vols: BTC=80%, ETH=100%, SOL=120% (conservative; operator review expected before live capital).
- Minimum τ = 1 second in years to avoid division-by-zero at expiry.
- Probability clamped to open interval `(0.005, 0.995)` — prevents extreme values from leaking into the soft entry rule as binary 0/1 signals.
- `annual_vol` override parameter allows per-call vol overrides without changing global table.
- All inputs and outputs are plain floats (not Decimal) — this is model output, not financial ledger arithmetic.
- `FairValueEstimate.assumptions` tuple carries operator-visible disclaimers into every output.

### accumulation_engine.py

- Pure function `evaluate_accumulation(state, config) -> AccumulationIntent` — no network, no side-effects, never raises.
- All financial values use `Decimal` for consistency with the paper ledger.
- Gate hierarchy (first failing gate terminates evaluation):
  1. **Feed gate** (hard): `feed_snapshot.is_usable` → `ACTION_FREEZE` if False or None. Freeze reason recorded in rationale.
  2. **Quote gate**: both YES and NO best-ask quotes present → `ACTION_SKIP` if missing.
  3. **Hard rule**: `YES_ask + NO_ask ≤ config.target_pair_cost_threshold` → `ACTION_SKIP` if fails.
  4. **Soft rule**: per-leg `ask < fair_prob` (vacuously passes if `fair_prob is None`).
- Partial-pair state awareness: `_classify_partial_state()` returns `"none" | "yes_only" | "no_only" | "both_legs"`. When `yes_only`, engine focuses only on completing the NO leg (and vice versa), subject to soft rule filter.
- `rationale` dict is always populated regardless of action — diagnostic visibility for operator logs.

---

## Test Results

```
tests/test_crypto_pair_reference_feed.py   29 passed
tests/test_crypto_pair_fair_value.py       45 passed
tests/test_crypto_pair_accumulation_engine.py  37 passed
Total: 111 passed, 0 failed
```

Full suite: 2,468 passed, 8 pre-existing failures (unrelated: `test_gate2_eligible_tape_acquisition` and `test_new_market_capture`).

---

## Pre-existing Failures (not introduced here)

- `tests/test_gate2_eligible_tape_acquisition.py` — `ResolvedWatch.regime` attribute missing (Gate 2 work not yet completed)
- `tests/test_new_market_capture.py` — live Gamma API dependency in tests (not offline-safe)

---

## Open Items

- `BinanceFeed.connect()` / live WS loop: present and functional but not yet wired to any CLI command or scheduler. Phase 1A follow-on work.
- Coinbase fallback feed: `feed_source` field reserved, implementation deferred.
- Fair value volatilities are conservative assumptions, not calibrated from live data. Operator review required before live capital.
- CLI wiring (`polytool crypto-pair` commands, scheduling, paper ledger integration) is Phase 1A follow-on work — explicitly out of scope for this packet.
