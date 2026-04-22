# Dev Log — SimTrader Fee Model Overhaul (Deliverable A)

**Date:** 2026-04-21
**Branch:** main
**Work packet:** Unified Open Source Integration Sprint — Deliverable A

## Objective

Fix three bugs in `packages/polymarket/simtrader/portfolio/fees.py`:
1. Taker-only fees — all fills charged as taker; makers actually pay zero on Polymarket.
2. Single undifferentiated fee rate — actual rates are category-specific.
3. No Kalshi model — zero Kalshi fee code in SimTrader.

## Director-Locked Decisions (pre-implementation)

- Deliverable A only (B and C deferred).
- Maker modeling = Option A: maker fee = zero; no rebate estimator in SimTrader.
- Backward-compatible two-path dispatch: `category` kwarg activates new exponent-1
  path; legacy `fee_rate_bps` path keeps exponent-2 formula unchanged.
- SimTrader must remain deterministic/offline-capable; no live API calls in sim path.
- Pydantic config migration out of scope.
- `packages/polymarket/fees.py` (float-based) not touched.

## Formula Verification

The corrected Polymarket taker fee formula (exponent-1):

```
fee_usdc = shares × category_rate × price × (1 − price)
```

Verified against acceptance criteria from the work packet:
- `100 × 0.072 × 0.50 × 0.50 = 1.80` (crypto) ✓
- `100 × 0.03 × 0.50 × 0.50 = 0.75` (sports) ✓

Legacy exponent-2 formula retained on `fee_rate_bps` path:
```
fee_usdc = shares × price × (fee_rate_bps / 10 000) × (price × (1−price))²
```

Kalshi formula:
```
fee_usdc = ceil(0.07 × contracts × price × (1 − price))
ceil(0.07 × 10 × 0.60 × 0.40) = ceil(0.168) = 0.17 ✓
```

No live `/fee-rate` endpoint call was made during this session.  The category
rates are sourced from the work packet spec (GLM-5 research, verified against
acceptance criteria math).  A one-time verification via `curl` or the CLI
`/fee-rate` endpoint is recommended before live capital deployment.

## Files Changed

| File | Change |
|---|---|
| `packages/polymarket/simtrader/portfolio/fees.py` | Core: added `POLYMARKET_CATEGORY_FEE_RATES`, updated `compute_fill_fee` with two-path dispatch, added `KalshiFeeModel` |
| `packages/polymarket/simtrader/portfolio/ledger.py` | Added `fee_category`, `fee_role` params; `_on_fill` forwards both to `compute_fill_fee`; `summary` exposes them |
| `packages/polymarket/simtrader/broker/rules.py` | Added `force_taker: bool = False` and `market_category: Optional[str] = None` to `Order` dataclass |
| `packages/polymarket/simtrader/config_loader.py` | Added `load_fee_config(config)` helper |
| `tests/test_simtrader_portfolio.py` | Added `POLYMARKET_CATEGORY_FEE_RATES`, `KalshiFeeModel` imports; added `TestComputeFillFeeCategories` (15 tests) and `TestKalshiFeeModel` (8 tests) |
| `docs/features/simtrader_fee_model_v2.md` | Feature doc |

## Files NOT Touched (per scope)

- `packages/polymarket/simtrader/broker/fill_engine.py`
- `packages/polymarket/fees.py` (float-based, separate module)
- `packages/polymarket/simtrader/strategies/crypto_pairs/`
- `packages/polymarket/execution/` and `kill_switch.py`, `risk_manager.py`
- Roadmap / CURRENT_STATE / CLAUDE docs

## Test Results

```
tests/test_simtrader_portfolio.py: 87 passed (was 64; +23 new)
Full suite (excl. pre-existing RIS cloud routing failures): 4118 passed, 0 new failures
```

Pre-existing failure: `test_ris_phase2_cloud_provider_routing.py` — 8 tests fail on
`_post_json` attribute missing from `providers.py`; unrelated to this work packet.

## Codex Review

Tier: Recommended (strategy/SimTrader core).
Review: Not yet run — run `/codex:review fees.py ledger.py --background` before next PR.

## Open Questions / Follow-On

1. **Live fee-rate verification** — Run `curl` against `/fee-rate` or add a CLI command
   to verify the category rates match production before live capital deployment.
2. **Per-fill taker/maker role detection** — Currently the role is a static ledger
   config. Actual role depends on whether the order is resting vs. crossing the book.
   Deferred to Deliverable B or a future Sprint.
3. **SPEC-0004 truth-sync** — The SPEC still documents the exponent-2 formula as
   canonical. Update after human review of this change.
4. **Kalshi wiring** — `KalshiFeeModel` is implemented but not wired into any replay
   or live runner. Deliverable C.
5. **`summary.json` schema** — Added `fee_category` and `fee_role` keys; downstream
   consumers of `summary.json` should handle these gracefully (they're new).
