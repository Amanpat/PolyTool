# Track A Week 1 — Live Execution Primitives

**Date:** 2026-03-05
**Branch:** simtrader
**Spec:** docs/specs/SPEC-0011-live-execution-layer.md

---

## Summary

Implemented the Stage-0 execution primitives for the live execution layer as
specified in SPEC-0011.  All code is fully offline-testable; no real network
calls are made by any test.  Dry-run is the default at every level.

---

## Files Touched

### New — execution package

| File | Purpose |
|------|---------|
| `packages/polymarket/simtrader/execution/__init__.py` | Package init; exports all public symbols |
| `packages/polymarket/simtrader/execution/kill_switch.py` | `KillSwitch` ABC + `FileBasedKillSwitch` |
| `packages/polymarket/simtrader/execution/rate_limiter.py` | `TokenBucketRateLimiter` with injectable clock/sleep |
| `packages/polymarket/simtrader/execution/risk_manager.py` | `RiskConfig` + `RiskManager` (pre-trade + halt) |
| `packages/polymarket/simtrader/execution/live_executor.py` | `OrderRequest`, `OrderResult`, `LiveExecutor` |
| `packages/polymarket/simtrader/execution/live_runner.py` | `LiveRunConfig`, `LiveRunner` (orchestrator) |

### Modified

| File | Change |
|------|--------|
| `tools/cli/simtrader.py` | Added `live` subcommand parser + `_live()` handler + dispatch |

### New — tests

| File | Tests |
|------|-------|
| `tests/test_live_execution.py` | 56 offline unit tests covering all primitives |

---

## Design Decisions

### Kill switch
- File-based: tripped when file exists and contains a truthy string (`1`, `true`, `yes`, `on`; case-insensitive).
- Absent or empty file = not tripped.
- `check_or_raise()` raises `RuntimeError("Kill switch is active: <path>")` — message is explicit and greppable.
- Called unconditionally before every place/cancel action, even in dry-run.

### Rate limiter
- Token-bucket algorithm; bucket starts full.
- Injectable `_clock` and `_sleep` callables allow tests to avoid real sleeps entirely.
- `try_acquire()` is non-blocking; `acquire()` sleeps the minimum needed time.
- Default in `LiveRunConfig`: 30/min (well under the 60/min ceiling).

### Risk manager
- Conservative Stage-0 defaults: `max_order_notional=25`, `max_position_notional=100`, `daily_loss_cap=15`, `max_inventory_units=1000` (all USD).
- `check_order()` returns `(allowed: bool, reason: str)` — never raises.
- `on_fill()` updates position state and inventory.
- `should_halt()` is sticky: once a daily-loss breach is detected, subsequent calls return the same halt reason.
- Halt check is embedded in `check_order()` so all gates collapse to a single call site.

### Live executor
- `dry_run=True` is the constructor default.
- In dry-run: kill switch is still checked; rate limiter is NOT called; client is NOT called.
- In live mode: kill switch → rate limiter → client (in that order).
- Minimal duck-typed client interface: `place_order(asset_id, side, price, size, post_only)` and `cancel_order(order_id)`.

### Live runner
- `LiveRunConfig.dry_run` defaults to `True`.
- `run_once(strategy_fn)` kill-switch-checks before calling the strategy.
- Each `OrderRequest` from the strategy is validated by `RiskManager.check_order` before the executor is called.
- Returns a summary dict: `{attempted, submitted, rejected, dry_run, reasons}`.

### CLI (`simtrader live`)
- `--no-dry-run` flag is required to disable dry-run; omitting it keeps dry-run active.
- Kill-switch path, rate limit, and all four risk parameters are configurable.
- Pre-flight kill-switch check with a clear error message before running.
- No-op strategy (returns `[]`) is used by default — Stage 0 safe.
- Prints JSON summary to stdout on success.

---

## Test Coverage

```
tests/test_live_execution.py — 56 tests

TestFileBasedKillSwitch     19 cases  (absent/empty/truthy/falsy/raise/clear)
TestTokenBucketRateLimiter   8 cases  (try_acquire, acquire, refill, overflow)
TestRiskManager             12 cases  (allow, reject, halt, sticky, defaults)
TestLiveExecutor            10 cases  (dry-run, kill-switch, live, rate-limit)
TestLiveRunner               7 cases  (dry-run, risk rejection, kill-switch, empty)
```

---

## pytest Output

```
===================== 1094 passed, 25 warnings in 38.76s ======================
```

(56 new tests; 1038 existing all still green.)

---

## Open Questions

1. **CLOB client interface** — The current executor accepts any duck-typed object.
   When Polymarket's official Python CLOB client is integrated, `place_order` /
   `cancel_order` signatures should be verified against actual API responses.

2. **Daily PnL tracking** — The current `RiskManager` tracks fee costs and sell
   revenue but does not model cost-basis accounting across restarts.  For multi-
   session use, `_daily_realized_pnl` and `_total_fees_paid` should be persisted
   to disk (e.g., a JSON file per trading day).

3. **Partial fill handling** — `on_fill()` assumes full fills for position
   tracking; partial fill sequences should be tested once a real fill event
   schema is confirmed.

4. **Gate enforcement** — SPEC-0011 requires replay → sweep → shadow gates
   before any live capital.  Gate documentation/enforcement is not automated;
   it is operator responsibility at Stage 0.
