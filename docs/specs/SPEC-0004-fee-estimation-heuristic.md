# SPEC-0004: Configurable Fee Estimation Heuristic

**Status**: Accepted  
**Created**: 2026-02-17

## Overview

Roadmap 4.3 adds deterministic, configurable fee estimation for scan trust artifacts.
The heuristic is applied from local `polytool.yaml` and used to compute a net-after-estimated-fees
PnL view without silently rewriting existing `realized_pnl_net`.

## Config

Source: local `polytool.yaml` under `fee_config`.

```yaml
fee_config:
  profit_fee_rate: 0.02
  source_label: "estimated"
```

Defaults when missing or invalid:

- `profit_fee_rate = 0.02`
- `source_label = "estimated"`

## Fee Estimation Rules

Applied per position using `gross_pnl` (fallback to `realized_pnl_net` only when `gross_pnl` is absent):

```text
if gross_pnl > 0:
    fees_estimated = gross_pnl * profit_fee_rate
    fees_source = source_label
else:
    fees_estimated = 0.0
    fees_source = "not_applicable"
```

## PnL Fields

Existing `realized_pnl_net` is retained as reported/source data.

A new derived field is added on each position:

```text
realized_pnl_net_estimated_fees = gross_pnl - fees_estimated
```

Coverage report totals and segment totals use the estimated-fee net variant, while gross totals are
reported alongside it.

## Coverage Report Schema Additions

- `pnl.gross_pnl_total`
- `pnl.gross_pnl_by_outcome`
- `pnl.realized_pnl_net_estimated_fees_total`
- `pnl.realized_pnl_net_estimated_fees_by_outcome`
- `pnl.reported_realized_pnl_net_total`
- `pnl.reported_realized_pnl_net_by_outcome`
- `fees.fees_source_counts` includes `estimated` (or configured label) and `not_applicable`
- `fees.fees_estimated_present_count` increments for profitable rows

Segment buckets now include both:

- `total_pnl_net` (net after estimated fees)
- `total_pnl_gross`

## Versioning

`coverage_reconciliation_report.json` schema version is bumped:

- from `report_version = "1.1.0"`
- to `report_version = "1.2.0"`
