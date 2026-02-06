# Strategy Playbook v0

**Purpose**: This document describes the methodology for validating trading hypotheses.
It does NOT claim any alpha or provide trading signals.

## Resolution Outcome Taxonomy

Every position must have exactly one resolution outcome:

| Outcome | Description | Determination |
|---------|-------------|---------------|
| `WIN` | Held to resolution, outcome won | settlement_price = 1.0 + position_remaining > 0 |
| `LOSS` | Held to resolution, outcome lost | settlement_price = 0.0 + position_remaining > 0 |
| `PROFIT_EXIT` | Exited before resolution at profit | position_remaining <= 0 + gross_pnl > 0 |
| `LOSS_EXIT` | Exited before resolution at loss | position_remaining <= 0 + gross_pnl <= 0 |
| `PENDING` | Market not yet resolved | settlement_price is NULL |
| `UNKNOWN_RESOLUTION` | Resolution data unavailable | Fallback when data missing |

## Win Rate Calculation

```
win_rate = (WIN + PROFIT_EXIT) / (WIN + LOSS + PROFIT_EXIT + LOSS_EXIT)
```

Exclude PENDING and UNKNOWN_RESOLUTION from win rate calculation.

## Expected Value Framework

For a given hypothesis about user behavior:

```
EV = P(correct_prediction) * avg_payout - P(incorrect_prediction) * avg_loss
```

Where:
- `P(correct_prediction)` = historical win rate for that hypothesis
- `avg_payout` = average payout when correct (1.0 - entry_price for binary WIN)
- `avg_loss` = average loss when incorrect (entry_price for binary LOSS)

## Falsification Framework

Every hypothesis must include:

1. **Claim**: The specific, testable statement
2. **Evidence**: Metrics/trade_uids supporting the claim
3. **Confidence**: high/medium/low
4. **Falsification Method**: How to disprove this hypothesis

Example:

| Claim | Evidence | Confidence | Falsification |
|-------|----------|------------|---------------|
| User enters positions 1-4 hours before event start | 75% of trades have minutes_before_start in [60, 240] | medium | Find trades with minutes_before_start > 1440 |

## Metrics for Validation

### Position-Level
- entry_price, exit_price
- hold_duration_seconds
- gross_pnl, realized_pnl_net
- resolution_outcome
- minutes_before_start (if available)

### User-Level (Rolling Window)
- win_rate (last 30/90 days)
- avg_position_size
- avg_hold_duration
- category_concentration
- market_coverage

### Risk Signals
- Concentration in single market/category > 50%
- Large position relative to historical average
- Deviation from typical entry timing

## Validation Checklist

Before accepting a hypothesis:

- [ ] Claim is specific and testable
- [ ] Evidence includes at least 3 supporting trade_uids
- [ ] Confidence level is justified
- [ ] Falsification method is actionable
- [ ] No cherry-picked evidence (reviewer checked)

## What This Playbook Does NOT Do

- Provide trading signals or recommendations
- Claim any alpha or edge
- Make predictions about future performance
- Guarantee accuracy of historical analysis

This is a methodology document for research purposes only.
