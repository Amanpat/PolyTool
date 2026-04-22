# Fee Model Overhaul — Propagation Fix

**Date:** 2026-04-21
**Scope:** Deliverable A propagation (B and C deferred per director decision)

## Problem

Deliverable A added `fee_category` and `fee_role` params to `PortfolioLedger.__init__`, but
every runtime entry point still constructed `PortfolioLedger` without those params. All
production runs (normal, sweep, shadow, Studio) were silently using the legacy exponent-2
taker-only formula regardless of market type.

## Changes

### Core propagation (all completed in prior + this session)

| File | Change |
|---|---|
| `packages/polymarket/simtrader/portfolio/ledger.py` | Deliverable A — added `fee_category`/`fee_role` params + dispatch logic |
| `packages/polymarket/simtrader/portfolio/fees.py` | Deliverable A — category-aware path, maker=zero (Option A) |
| `packages/polymarket/simtrader/strategy/runner.py` | Pass `fee_category`/`fee_role` from `StrategyRunner` → `PortfolioLedger` |
| `packages/polymarket/simtrader/strategy/facade.py` | Added `fee_category`/`fee_role` fields to `StrategyRunParams` frozen dataclass |
| `packages/polymarket/simtrader/sweeps/runner.py` | Added to `SweepRunParams`; propagated through `_apply_overrides` → `StrategyRunParams`; included in manifest `base_config` |
| `packages/polymarket/simtrader/shadow/runner.py` | Pass `fee_category`/`fee_role` from `ShadowRunner.__init__` → `PortfolioLedger` |
| `packages/polymarket/simtrader/studio/ondemand.py` | Added to `OnDemandSession.__init__` and `OnDemandSessionManager.create()`; wired into all 5 `PortfolioLedger` constructions (save_artifacts, reset_runtime_state, rebuild_activity_feed, replay_for_artifacts, restore_checkpoint) |
| `packages/polymarket/simtrader/studio/app.py` | Parse `fee_category`/`fee_role` from HTTP body in `ondemand_new()` handler; pass to `_ondemand_sessions.create()` |
| `tools/gates/mm_sweep.py` | Pass `fee_category=tape.bucket, fee_role="taker"` to `SweepRunParams` so Gate 2 sweeps use per-bucket category rates |
| `tools/cli/simtrader.py` | Wire `load_fee_config()` at all 4 `StrategyRunParams`/`SweepRunParams` construction sites: `_run()`, `_sweep()`, quickrun sweep mode, quickrun single-run mode |

### CLI wiring pattern

```python
from packages.polymarket.simtrader.config_loader import load_fee_config as _load_fee_config
_fee_cfg = _load_fee_config(strategy_config)
fee_category = _fee_cfg.get("market_category")
# ... passed as fee_category=fee_category, fee_role="taker" in StrategyRunParams/SweepRunParams
```

Users can set `market_category` in the strategy config `fees:` block to activate the
category-aware fee path (linear, Polymarket platform rates).

## Tests

Added `TestLedgerFeeModelPropagation` (7 tests) to `tests/test_simtrader_portfolio.py`:

- Category path is used (and produces different amount than legacy) when `fee_category` set
- Maker role → zero fee regardless of category
- Taker role with known categories (sports, politics, crypto) → non-zero fee
- No `fee_category` → legacy path identical to `fee_rate_bps=200`
- `summary()` records `fee_category` and `fee_role` for artifact self-description

## Test Results

```
tests/test_simtrader_portfolio.py: 93 passed
Full suite: 2606 passed, 1 pre-existing failure (test_gemini_provider_success —
  AttributeError on providers._post_json, unrelated to fee changes)
```

## Constraints Honoured

- Deliverable B (broker-sim taker/maker classification) and C (StrategyRunner injection) deferred
- Maker fee = zero (Option A) — no rate lookup needed for maker fills
- No Pydantic migration
- No broad refactors beyond the propagation path
- Not pushed to main

## Codex Review

Tier: Recommended (SimTrader core). No adversarial review required (no execution/kill-switch paths touched). Review not run — scope is portfolio-layer plumbing only.

## Open Items

- `fee_role="taker"` is hardcoded at all CLI sites; broker-side taker/maker classification (Deliverable B) will make this dynamic when shipped.
- Studio UI does not yet expose `fee_category`/`fee_role` inputs in the web form.
