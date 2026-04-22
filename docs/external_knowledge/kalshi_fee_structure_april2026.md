---
title: "Kalshi Fee Structure (April 2026)"
freshness_tier: CURRENT
confidence_tier: PRACTITIONER
validation_status: UNTESTED
source_family: external_knowledge
source_quality_caution: >
  Derived from secondary packet references and indirect Kalshi documentation summaries.
  Verify exact fee formula, rounding semantics, fee-waiver fields, and maker/taker
  treatment against official Kalshi API docs or regulatory filings before treating
  as definitive.
---

# Kalshi Fee Structure (April 2026)

## Standard Fee Formula

```
fee = round_up(0.07 * C * P * (1 - P))
```

Where:
- `C` = contracts traded
- `P` = price in **dollars** on the 0.01 to 0.99 scale (not the 0–1 probability scale)
- The result rounds **up** to the nearest cent

The shape is identical to Polymarket's `p * (1 - p)` curve, but with a fixed `0.07`
multiplier rather than a per-category table. The rounding-up behavior matters for small
trades: a trade producing a sub-cent fee result is rounded to $0.01 rather than $0.00.

## Worked Example

Entry at P = 0.50, C = 10 contracts:
```
fee = round_up(0.07 * 10 * 0.50 * 0.50)
    = round_up(0.07 * 2.50)
    = round_up(0.175)
    = $0.18
```

Entry at P = 0.20, C = 5 contracts:
```
fee = round_up(0.07 * 5 * 0.20 * 0.80)
    = round_up(0.07 * 0.80)
    = round_up(0.056)
    = $0.06
```

## Maker/Taker Distinction

Kalshi does distinguish maker and taker roles. Some markets may expose `fee_waiver`
fields or receive special fee treatment in specific market types. The standard 0.07
formula applies to general taker fills; maker treatment differs and should be confirmed
against current API metadata.

## Liquidity Incentive Program

Kalshi operates a Liquidity Incentive Program (LIP) that is separate from the standard
fee schedule. Do not merge LIP rewards with the standard fee calculation. LIP terms
and eligibility may differ across market categories and contract types.

## Fee-Change History

Fee rates and structures have changed over time. The packet notes a `fee_changes` API
field or metadata path for per-market historical fee data. When computing historical
PnL, use per-market fee history rather than the current rate table.

## Cross-Platform Normalization

Kalshi's framing differs from Polymarket's in two ways that matter for comparison:

| Dimension | Kalshi | Polymarket |
|-----------|--------|-----------|
| Price scale | Cents (0.01–0.99) | Probability (0.01–0.99, treated as shares) |
| Base unit | Contracts ($1 par) | Shares ($1 par equivalent) |
| Fee multiplier | Fixed 0.07 | Category table (0.03–0.072) |

Normalize both sides to a common probability scale and notional basis before computing
cross-platform fee differentials or net PnL comparisons.
