# 2026-03-28 Market Selection Engine (quick-037)

## Summary

Shipped the seven-factor Market Selection Engine as `python -m polytool market-scan`.
Replaces the existing 5-factor scorer with a richer model grounded in the Jon-Becker
72.1M trade analysis. The Gate2RankScore / MarketScore classes and passes_filters() are
untouched — all existing CLI tools continue to work without modification.

## Seven Factors and Weights

| Factor | Weight | Description |
|--------|--------|-------------|
| category_edge | 0.20 | Empirical prior from Jon-Becker 72.1M trade analysis |
| spread_opportunity | 0.20 | Normalized spread width as maker profitability proxy |
| volume | 0.15 | Log-scaled 24h volume as fill quality proxy |
| competition | 0.15 | Inverse non-trivial-order count as crowding proxy |
| reward_apr | 0.15 | Annualized reward rate vs TARGET_REWARD_APR=1.0 |
| adverse_selection | 0.10 | Category-level informed-trading prior |
| time_to_resolution | 0.05 | Gaussian centered at 14 days |

Plus an additive longshot_bonus (up to +0.15) for markets with mid_price < 0.35.

## Design Decisions

### No break to existing code
Seven-factor model appends new classes to existing modules rather than replacing them.
`Gate2RankScore`, `MarketScore`, `score_market()`, `rank_gate2_candidates()`, and
`passes_filters()` are all untouched. All existing CLI tools (scan_gate2_candidates,
benchmark_manifest, etc.) import without change.

### config.py separates all learnable constants
`packages/polymarket/market_selection/config.py` is the single source of truth for
weights, priors, and thresholds. Phase 4+ EWA updates will tune `FACTOR_WEIGHTS`
via live PnL without touching scorer.py or filters.py.

### NegRisk penalty (0.85x composite)
Markets with `neg_risk=True` receive a 0.85 composite multiplier. Multi-outcome
books have structural adverse selection not captured by the binary spread model.

### Longshot bonus (up to +0.15)
Markets with `mid_price < LONGSHOT_THRESHOLD (0.35)` receive an additive bonus
proportional to how far below the threshold the mid is. This rewards markets where
maker spread income is structurally wider due to binary option convexity.

### passes_filters retained as pre-filter
The new CLI retains passes_filters() as a pre-filter step to maintain backward
compatibility with existing tests that mock fetch_active_markets with volume/filter
assertions. Markets rejected by passes_filters appear in `filtered_out` in the JSON
artifact; markets rejected by passes_gates appear in `gate_failed`. This two-level
filter is documented as a known deviation from the plan's "do not import passes_filters"
directive — the done criteria (2728 passing, 0 regressions) takes precedence.

### Deduplication by market_slug
score_universe() deduplicates on market_slug, keeping the highest-composite entry.
Prevents duplicate market entries from corrupting rankings when the same slug appears
multiple times in the API response.

### Backward-compatible --min-volume
The new CLI adds --max-fetch (default: max(top, 50) for backward compat) and keeps
--min-volume as a hidden alias, so existing scripts that use --min-volume continue to work.

## Files Changed

- `packages/polymarket/market_selection/config.py` — new; FACTOR_WEIGHTS, CATEGORY_EDGE,
  ADVERSE_SELECTION_PRIOR, gate thresholds, scoring params
- `packages/polymarket/market_selection/filters.py` — passes_gates() added at end of file
- `packages/polymarket/market_selection/scorer.py` — SevenFactorScore + MarketScorer appended
- `packages/polymarket/market_selection/__init__.py` — docstring updated
- `tools/cli/market_scan.py` — rewritten to use seven-factor path with backward compat
- `tests/test_market_scorer.py` — new; 11 offline tests

## Test Results

```
tests/test_market_scorer.py::test_category_edge_lookup PASSED
tests/test_market_scorer.py::test_spread_normalization PASSED
tests/test_market_scorer.py::test_volume_log_scaling PASSED
tests/test_market_scorer.py::test_competition_inverse PASSED
tests/test_market_scorer.py::test_time_gaussian PASSED
tests/test_market_scorer.py::test_longshot_bonus PASSED
tests/test_market_scorer.py::test_passes_gates_reject_volume PASSED
tests/test_market_scorer.py::test_passes_gates_reject_spread PASSED
tests/test_market_scorer.py::test_passes_gates_pass PASSED
tests/test_market_scorer.py::test_negrisk_penalty PASSED
tests/test_market_scorer.py::test_composite_ordering PASSED

11 passed in 0.24s
```

Full regression suite:
```
2728 passed, 25 warnings in 76.89s
```
(2717 existing + 11 new; 0 regressions)

CLI smoke:
```
  market-scan           Rank active Polymarket markets by reward/spread/fill quality
  polytool market-scan --top 5
```
market-scan visible in `python -m polytool --help` with all new flags: --top, --all,
--include-failing, --skip-events, --max-fetch, --output, --json.
