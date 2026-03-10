# Dev Log: RiskManager Adverse-Selection Signals

**Date:** 2026-03-10
**Branch:** simtrader
**Author:** Track A / Phase 1 hardening

## Summary

Added VPIN and competing-MM-withdrawal adverse-selection signals to the
risk/control path.  Both signals degrade safely to no-trigger when required
inputs are absent.

## What changed

### New file: `packages/polymarket/simtrader/execution/adverse_selection.py`

Two signal classes and one guard:

- **`OFISignal`** (Order-Flow Imbalance, VPIN proxy) — uses the tick rule
  on mid-price changes to approximate buy/sell pressure.  True VPIN requires
  trade-tick volume with aggressor-side tagging; our tape format does not
  provide that (`last_trade_price` events carry price only, no size or
  direction).  The proxy classifies each mid-price move as a buy (+1) or sell
  (-1) tick.  Imbalance = |buy - sell| / total.  Triggers when imbalance >
  `threshold` and at least `min_samples` classified ticks are in the rolling
  window.

- **`MMWithdrawalSignal`** — tracks rolling total size across top-N BBO
  levels.  Triggers when current depth < `depth_drop_threshold` x rolling
  average, indicating other MMs are withdrawing quotes.

- **`AdverseSelectionGuard`** — wraps both signals.  `on_book_update(book)`
  feeds the current `L2Book` to both signals.  `check()` returns
  `GuardResult(blocked, reason, signals)`.  Either signal triggering is
  sufficient to block.  Safe to call with `None` book (no-op).

### Missing-data / cold-start policy

| Condition | OFISignal | MMWithdrawalSignal |
|---|---|---|
| No book update ever | `cold_start` -> no-trigger | `cold_start` -> no-trigger |
| Fewer than `min_samples` classified ticks | `warming_up` -> no-trigger | `warming_up` -> no-trigger |
| All ticks neutral (mid unchanged) | `neutral` -> no-trigger | — |
| Baseline depth is zero (empty book) | — | `zero_baseline` -> no-trigger |

### Modified: `packages/polymarket/simtrader/execution/risk_manager.py`

- `RiskManager.__init__` accepts optional `adverse_selection` kwarg
  (duck-typed; must expose `on_book_update(book)` and `check()`).
- New `RiskManager.on_book_update(book)` — feeds book to guard; no-op when
  no guard configured.
- `check_order` runs the adverse-selection gate as check 0, before price /
  size / notional validation.  Returns `(False, "risk: adverse_selection — …")`
  when blocked.

### Modified: `packages/polymarket/simtrader/execution/live_runner.py`

- `LiveRunner.run_once` accepts optional keyword argument `book=None`.
- When provided, calls `self._risk.on_book_update(book)` at the start of
  the tick, before the kill-switch check.

## What was NOT implemented / honest gaps

- **True VPIN** — requires trade-tick volume with aggressor-side tagging.
  The tape format does not expose this.  The OFI proxy uses direction of
  mid-price movement as a coarse surrogate.  This is documented in the
  module docstring.
- **Strategy-level spread widening** — the signals connect to the risk
  pre-trade gate (suppresses new quoting outright) rather than dynamically
  widening the A-S spread.  Spread widening via strategy override is deferred
  to a future hardening pass if the suppression behaviour proves too
  aggressive.
- **Session-pack / scanner / API/UI changes** — none; per scope.

## Tests

New file: `tests/test_adverse_selection.py` — 30 test functions covering:
- Construction guard errors for both signal classes
- Cold-start and warming-up no-trigger behaviour
- Trigger and no-trigger under normal conditions
- Missing-data degradation paths (None mid, empty book, zero baseline)
- `AdverseSelectionGuard` combining both signals
- `RiskManager` integration (with/without guard, guard check called in check_order)
- `LiveRunner` smoke test (book kwarg forwarded to risk manager)

## Manual verification

```bash
# Run all adverse-selection tests
python -m pytest tests/test_adverse_selection.py -v --tb=short

# Run full test suite (confirm no regressions)
python -m pytest tests/ -v --tb=short -q
```

## Risk / rollback

- No existing public interfaces changed.
- `RiskManager(RiskConfig())` — zero-arg construction still works; guard defaults to None.
- `LiveRunner.run_once(fn)` — old call sites (no `book=`) still work; `book` is keyword-only with default `None`.
- All new code is additive.  To roll back: revert the two modified files and delete `adverse_selection.py` and the test file.
