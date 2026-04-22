---
title: "Polymarket Fee Structure (April 2026)"
freshness_tier: CURRENT
confidence_tier: PRACTITIONER
validation_status: UNTESTED
source_family: external_knowledge
source_quality_caution: >
  Derived from corrected internal notes and secondary packet references. Verify
  category fee rates, maker rebate split ratios, and /fee-rate endpoint behavior
  against primary Polymarket documentation before treating as definitive.
---

# Polymarket Fee Structure (April 2026)

## Taker Fee Formula

All taker fills on Polymarket use the same probability-quadratic formula:

```
fee = C * feeRate * p * (1 - p)
```

Where:
- `C` = filled shares (contract count)
- `feeRate` = category-specific rate (see table below)
- `p` = fill price on the 0-1 probability scale

The `p * (1 - p)` multiplier means fees are highest at p = 0.50 (maximum uncertainty)
and approach zero as outcomes near certainty. Fees are charged to takers only; makers
do not pay a per-fill fee.

## Category Fee Rates

| Category | feeRate |
|----------|---------|
| Crypto | 0.072 |
| Sports | 0.03 |
| Finance / Politics / Mentions / Tech | 0.04 |
| Economics / Culture / Weather / Other | 0.05 |
| Geopolitics | 0 (fee-free) |

Geopolitics markets have no ordinary taker fee burden.

Token-specific `/fee-rate` API responses may return values that differ from this
broad category table, especially for crypto markets. Always prefer token-level
data at execution time.

## Maker Rebates

Makers receive rebates, but these are NOT negative per-fill fees. They are:
- Calculated daily at the market level, not on each individual fill.
- Funded from a share of accumulated taker fees in that market.
- Allocated proportionally using the same `fee_equivalent = C * feeRate * p * (1 - p)`
  weighting as taker fees, applied to the maker's fills.

Rebate pool split:
- **Crypto markets**: 20% of taker fees redistributed to makers
- **Other fee-paying categories**: 25% of taker fees redistributed to makers

## Q-Score vs Maker Rebates

Q-score (liquidity rewards) and maker rebates are two distinct incentive programs.
Do not conflate them. Q-score rewards depend on quoting behavior; maker rebates
depend on filled volume and timing within the daily settlement cycle.

## Key Implications for SimTrader / Strategy Evaluation

- Net fee per fill at midpoint p = 0.50 and category feeRate = 0.04:
  `fee = C * 0.04 * 0.50 * 0.50 = C * 0.01` (1% of notional per fill, shares-based)
- Crypto taker fees are roughly 2.4x politics/finance rates at the same price level.
- Maker strategies in crypto still face zero per-fill cost but receive a smaller rebate
  pool share (20%) than equivalent strategies in sports (25%).
- Geopolitics is entirely free to both sides from a taker-fee perspective.
