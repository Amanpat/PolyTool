# FEATURE: Configurable Fee Estimation in Scan Trust Artifacts

Scan reports now estimate fees for profitable positions so the headline net PnL reflects a simple fee haircut instead of raw gross profits, while still preserving the original reported PnL and gross totals for comparison.

**Shipped**: 2026-02-17  
**Roadmap**: 4.3

## What shipped

- New local config in `polytool.yaml`:
  - `fee_config.profit_fee_rate` (default `0.02`)
  - `fee_config.source_label` (default `"estimated"`)
- Fee heuristic is now applied to all rows with positive `gross_pnl`, including `PROFIT_EXIT`.
- Every position now gets `realized_pnl_net_estimated_fees = gross_pnl - fees_estimated`.
- Coverage report PnL totals and segment totals now use the estimated-fee net variant.
- Coverage report still includes gross and reported-source PnL for side-by-side auditing.
- `fees_source_counts` includes `estimated`/configured label and `not_applicable`.
- `fees_estimated_present_count` increases when profitable positions exist.

## Behavior

```text
if gross_pnl > 0:
    fees_estimated = gross_pnl * profit_fee_rate
    fees_source = source_label
else:
    fees_estimated = 0.0
    fees_source = "not_applicable"
```

Pending positions without sells continue to normalize to zero realized/gross PnL and therefore stay
`not_applicable`.

## Related docs

- `docs/specs/SPEC-0004-fee-estimation-heuristic.md`
- `docs/adr/0007-fee-estimation-2pct-profit.md`
