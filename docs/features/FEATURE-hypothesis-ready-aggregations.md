# Feature: Hypothesis-Ready Segment Aggregations (Roadmap 5.3)

## Summary

This feature turns per-position CLV and entry-context fields into segment-level hypothesis signals.
For every dimension bucket (entry price tier, market type, league, sport, category) the coverage
report now emits both count-weighted and notional-weighted variants of key metrics, along with
explicit denominators so every number is verifiable. A new **Hypothesis Signals** markdown section
surfaces top-performing segments by weighted CLV and beat-close rate, giving a deterministic,
offline-safe starting point for hypothesis formation — no guessing, no magic.

---

## Metric Definitions

### Count-Weighted (new fields)

| Field | Definition | Denominator |
|---|---|---|
| `avg_entry_drift_pct` | Mean `(price_at_entry - price_1h_before_entry) / price_1h_before_entry` | `avg_entry_drift_pct_count_used` (positions where both prices present and `price_1h_before_entry > 0`) |
| `movement_up_rate` | Fraction of positions with `movement_direction == "up"` | `count` (all positions in bucket) |
| `movement_down_rate` | Fraction of positions with `movement_direction == "down"` | same |
| `movement_flat_rate` | Fraction of positions with `movement_direction == "flat"` | same |
| `movement_unknown_rate` | Fraction of positions with movement_direction absent or unrecognized | same |
| `avg_minutes_to_close` | Mean of `minutes_to_close` | `minutes_to_close_count_used` |
| `median_minutes_to_close` | Median of `minutes_to_close` | `minutes_to_close_count_used` |

**Invariant:** `movement_up_rate + movement_down_rate + movement_flat_rate + movement_unknown_rate == 1.0`
when `count > 0`. All four rates are `None` when `count == 0`.

Existing fields now include explicit denominators:

| Field | New denominator field |
|---|---|
| `avg_clv_pct` | `avg_clv_pct_count_used` |
| `beat_close_rate` | `beat_close_rate_count_used` |

### Notional-Weighted (new fields)

Weighting variable: `position_notional_usd`. Positions with missing or zero notional are **skipped**
for weighted metrics but still counted in count-weighted metrics.

| Field | Definition | Weight denominator |
|---|---|---|
| `notional_weighted_avg_clv_pct` | `sum(clv_pct × notional) / sum(notional)` | `notional_weighted_avg_clv_pct_weight_used` |
| `notional_weighted_beat_close_rate` | `sum(beat_close × notional) / sum(notional)` | `notional_weighted_beat_close_rate_weight_used` |
| `notional_weighted_avg_entry_drift_pct` | `sum(entry_drift_pct × notional) / sum(notional)` | `notional_weighted_avg_entry_drift_pct_weight_used` |
| `notional_w_total_weight_used` | Total notional USD included in any weighted metric for this bucket | — |

All notional-weighted fields are `None` when the respective weight denominator is zero.

---

## entry_drift_pct Definition

Per SPEC-0009 `price_at_entry` is the `nearest_prior_to_entry` price sample.

```
entry_drift_pct = (price_at_entry - price_1h_before_entry) / price_1h_before_entry
```

Computed only when:
- `price_at_entry` is present and not None
- `price_1h_before_entry` is present and not None
- `price_1h_before_entry > 0`

Otherwise the position contributes 0 to `avg_entry_drift_pct_count_used` and the denominator
is not inflated.

---

## Segment Analysis JSON Schema (amendment)

Each bucket in `by_entry_price_tier`, `by_market_type`, `by_league`, `by_sport`, `by_category`
gains these additional keys (all nullable where defined above):

```json
{
  "avg_clv_pct_count_used": 3,
  "beat_close_rate_count_used": 3,
  "avg_entry_drift_pct": 0.05,
  "avg_entry_drift_pct_count_used": 3,
  "movement_up_rate": 0.333333,
  "movement_down_rate": 0.333333,
  "movement_flat_rate": 0.333333,
  "movement_unknown_rate": 0.0,
  "avg_minutes_to_close": 1440.0,
  "median_minutes_to_close": 1440.0,
  "minutes_to_close_count_used": 3,
  "notional_weighted_avg_clv_pct": 0.12,
  "notional_weighted_avg_clv_pct_weight_used": 300.0,
  "notional_weighted_beat_close_rate": 0.667,
  "notional_weighted_beat_close_rate_weight_used": 300.0,
  "notional_weighted_avg_entry_drift_pct": 0.04,
  "notional_weighted_avg_entry_drift_pct_weight_used": 300.0,
  "notional_w_total_weight_used": 300.0
}
```

`segment_analysis` also gains a top-level `hypothesis_meta` block:

```json
{
  "hypothesis_meta": {
    "notional_weight_total_global": 900.0,
    "min_count_threshold": 5
  }
}
```

---

## Markdown: Hypothesis Signals Section

The `coverage_reconciliation_report.md` now includes a **Hypothesis Signals** section after
"Entry Context Coverage". It contains:

1. CLV coverage rate + eligible-positions denominator
2. Entry context field coverage rates + denominators
3. Notional-weighted global denominator (total USD notional included)
4. Top 5 segments by `notional_weighted_avg_clv_pct` (min 5 positions)
5. Top 5 segments by `notional_weighted_beat_close_rate` (min 5 positions)

**Sort rule for Top Segments:** descending by metric, then ascending by segment name (tie-break).
This is fully deterministic — no randomness, no heuristics.

**min_count threshold:** controlled by `TOP_SEGMENT_MIN_COUNT = 5` constant in `coverage.py`.

---

## Notional Weighting Source Order

The helper `extract_position_notional_usd(pos)` resolves the notional USD for each position
using the following priority chain (first positive finite value wins):

| Priority | Field | Notes |
|---|---|---|
| 1 | `position_notional_usd` | Explicit notional field — used when present and > 0 |
| 2 | `total_cost` | Total cost paid for the position; common in raw dossier records |
| 3 | `size × entry_price` | Computed fallback when `size` and `entry_price` are both available and `entry_price > 0` |

Returns `None` (position skipped for weighted metrics) when no source yields a positive value.

This makes notional-weighted metrics populate automatically for dossier-sourced positions that
carry `total_cost` even when `position_notional_usd` is absent.

---

## Guardrails

- Never divide by zero: all denominators are checked before division.
- No invented values: fields are `None` when input data is missing.
- Notional zero treated same as missing: `position_notional_usd == 0` is excluded from weighted metrics.
- Movement rates always sum to 1.0 (or are all `None`): partition is exact.
- Top Segments only include segments with `count >= TOP_SEGMENT_MIN_COUNT`.

---

## Files Changed

- `polytool/reports/coverage.py` — core aggregation + markdown rendering
- `tests/test_coverage_report.py` — new `TestHypothesisReadyAggregations` class (14 tests)

---

## How to Verify

```bash
pytest tests/test_coverage_report.py -q
# 107 passed

pytest -q
# full suite clean
```

After a real scan run, inspect `coverage_reconciliation_report.md` for:

- `## Hypothesis Signals` section
- `### Top Segments by notional_weighted_avg_clv_pct`
- `### Top Segments by notional_weighted_beat_close_rate`
- `notional_weight_total_global` in the segment JSON

---

## Notional Parity Guarantee

Before segment analysis runs, `scan.py` normalizes `position_notional_usd` onto every position dict
using the following priority chain (implemented in `extract_position_notional_usd` in
`polytool/reports/coverage.py`):

1. `position_notional_usd` — explicit field if present and positive
2. `total_cost` — cost basis from dossier positions (most common real-world source)
3. `size * entry_price` — computed from raw position fields

Non-numeric values are silently skipped. Positions that yield `None` from all three sources
contribute 0 to the notional denominator and are excluded from notional-weighted metrics (they
still count in count-weighted metrics).

This normalization runs in `_normalize_position_notional()` in `tools/cli/scan.py` and is applied
to the `positions` list *before* `build_coverage_report` is called, ensuring `coverage.py` always
sees a populated `position_notional_usd` when any source field is available.

### Debug Artifact

Every scan run emits `notional_weight_debug.json` in the run root with:

| Field | Description |
|---|---|
| `total_positions` | Count of all positions |
| `extracted_weight_total` | Sum of all extracted `position_notional_usd` values |
| `count_missing_weight` | Positions where no source field yielded a positive value |
| `top_missing_reasons` | Reason breakdown: `NO_FIELDS`, `NON_NUMERIC`, `ZERO_OR_NEGATIVE`, `FALLBACK_FAILED` |
| `samples` | First 10 positions with their field presence and extracted value |

The path is recorded as `notional_weight_debug_json` in `run_manifest.output_paths`.
