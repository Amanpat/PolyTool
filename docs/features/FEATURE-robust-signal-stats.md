# Feature: Robust Segment Stats (Median, Trimmed Mean, IQR)

## Status
Implemented — Quick-007 (2026-02-20)

## Motivation
`avg_clv_pct` and `avg_entry_drift_pct` are sensitive to outliers. Large positive or negative positions can skew the mean, making a segment look stronger or weaker than it actually is. Median and trimmed mean provide more robust central-tendency estimates.

## What Was Added

### New fields per segment bucket (in `segment_analysis.json`)

For each dimension bucket (by_league, by_sport, by_market_type, by_entry_price_tier, by_category, by_market_slug):

| Field | Description |
| --- | --- |
| `median_clv_pct` | Median of raw clv_pct values in the bucket |
| `trimmed_mean_clv_pct` | 10% symmetric trimmed mean (count-based: removes floor(n*0.10) from each tail) |
| `p25_clv_pct` | 25th percentile (nearest-rank) |
| `p75_clv_pct` | 75th percentile (nearest-rank) |
| `robust_clv_pct_count_used` | Number of values used (capped at MAX_ROBUST_VALUES=500) |
| `median_entry_drift_pct` | Median of raw entry_drift_pct values |
| `trimmed_mean_entry_drift_pct` | 10% symmetric trimmed mean for entry drift |
| `p25_entry_drift_pct` | 25th percentile |
| `p75_entry_drift_pct` | 75th percentile |
| `robust_entry_drift_pct_count_used` | Number of values used |

### Leaderboard Markdown
The `## Top Segment Detail` section now shows `median_clv_pct` and `trimmed_mean_clv_pct` alongside `avg_clv_pct` when available.

## Implementation Notes
- **No new dependencies**: stdlib `math`, `statistics` not used — manual sort-based computation.
- **Memory safety**: Raw value lists are capped at `MAX_ROBUST_VALUES = 500`. Values are collected in arrival order (deterministic given consistent position ordering from scan output).
- **Trim definition**: 10% count-based symmetric trim removes `floor(n * 0.10)` values from each tail. With n < 10 items, trim_k = 0 (no trim, equivalent to mean).
- **Percentile definition**: Nearest-rank method: `sorted_vals[ceil(n * p) - 1]` (0-indexed).
- **Existing metrics untouched**: `avg_clv_pct`, `notional_weighted_avg_clv_pct`, and all other existing fields are unchanged.

## Files Changed
- `polytool/reports/coverage.py`: `_compute_robust_stats()`, `_empty_segment_bucket()`, `_accumulate_segment_bucket()`, `_finalize_segment_bucket()`, `_build_hypothesis_candidates()`
- `tools/cli/batch_run.py`: `_build_markdown()` Top Segment Detail section
- `tests/test_coverage_report.py`: `TestRobustStats` class (9 tests)
- `tests/test_batch_run.py`: `test_build_markdown_includes_robust_clv_stats`
