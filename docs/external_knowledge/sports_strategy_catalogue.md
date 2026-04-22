---
title: "Sports Strategy Catalogue"
freshness_tier: CURRENT
confidence_tier: PRACTITIONER
validation_status: UNTESTED
source_family: external_knowledge
source_quality_caution: >
  Parameter values and behavioral descriptions derived from internal reference-extract
  dev log (2026-04-21). Upstream strategy files carry mixed-license provenance.
  This document contains only behavioral summaries and parameter tables — no source
  expressions, no code, no pseudocode. Do not present these strategies as proven
  profitable; no published backtest results were found.
---

# Sports Strategy Catalogue

## Overview

Three reference signal patterns implemented for Polymarket sports prediction markets
as part of PolyTool's Track 1C work. These are parameter-reference entries, not
validated alpha. No published backtest results exist; treat these as behavioral
specifications for further evaluation.

All three strategies are registered in `STRATEGY_REGISTRY` and operate against
SimTrader's event-replay infrastructure.

---

## Strategy 1: Final Period Momentum (SportsMomentum)

**Behavioral description**: Activates during a configurable final window before
market close. Enters when price crosses above a threshold, targeting a take-profit
before resolution. Uses a stop-loss to limit downside.

**Reference defaults**:

| Parameter | Default Value |
|-----------|--------------|
| `final_period_minutes` | 30 |
| `entry_price` | 0.80 |
| `take_profit_price` | 0.92 |
| `stop_loss_price` | 0.50 |
| `trade_size` | 100 (tick variants) |

**Key behavioral notes**:
- Activation is clock-window based: the strategy only considers entry during the
  final `final_period_minutes` before the scheduled close time.
- Entry triggers on a below-to-above price cross at `entry_price`, not on any price
  above the threshold.
- Both quote-feed and trade-feed variants exist, differing in signal input source.

---

## Strategy 2: Late Favorite Limit Hold (SportsFavorite)

**Behavioral description**: A limit-entry favorite thesis. Enters a position when
price drops to or below an entry threshold, then holds to resolution rather than
using an in-strategy take-profit or stop-loss.

**Reference defaults**:

| Parameter | Default Value |
|-----------|--------------|
| `entry_price` | 0.90 |
| `trade_size` | 25 |
| Activation window | Optional (configurable) |
| Take-profit / stop-loss | None (hold-to-resolution) |

**Key behavioral notes**:
- No in-strategy exit other than resolution. Outcome is binary: full win or full loss.
- Optional activation window can restrict entries to a specific pre-close period.
- Position sizing is quantity-based; constrained by visible liquidity and affordability.

---

## Strategy 3: VWAP Reversion (SportsVWAP)

**Behavioral description**: A rolling tick-based mean-reversion pattern. Computes
a volume-weighted average price over a recent window and enters when price deviates
sufficiently, exiting when it reverts.

**Reference defaults**:

| Parameter | Default Value |
|-----------|--------------|
| `vwap_window` | 80 (ticks) |
| `entry_threshold` | 0.008 |
| `exit_threshold` | 0.002 |
| `take_profit` | 0.015 |
| `stop_loss` | 0.02 |

**Key behavioral notes**:
- The VWAP window is tick-count-based, not clock-based. Signal depends on recent
  price-size observations, not a fixed calendar window.
- Entry occurs when `|price - vwap| > entry_threshold`; exit when deviation falls
  below `exit_threshold`.
- Both quote and trade feed variants exist; they differ in which events feed the
  VWAP computation.
- Position sizing is quantity-based, constrained by visible liquidity.

---

## Cross-Strategy Notes

- All three strategies are tested against SimTrader tape replay. Accuracy of replay
  results depends on tape quality (Gold > Silver > Bronze).
- None of these strategies have published live or paper-soak results as of April 2026.
- Parameter sensitivity has not been systematically swept; the listed defaults are
  initial reference values from the PolyTool implementation.
- Sports markets on Polymarket use the `feeRate = 0.03` tier — significantly lower
  than crypto (0.072). This improves the breakeven spread requirement.
