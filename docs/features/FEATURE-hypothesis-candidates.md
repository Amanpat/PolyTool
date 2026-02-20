# Feature: Hypothesis Candidates Artifact (Roadmap 5.4)

## Summary

Produces `hypothesis_candidates.json` in the scan run root and a **Hypothesis Candidates**
section in `coverage_reconciliation_report.md`. Each entry is a top segment with a metrics
snapshot, explicit denominators, and a falsification plan.

## Candidate Selection Rules

- Only segments with `count >= TOP_SEGMENT_MIN_COUNT` (currently 5) are eligible.
- Ranked by `notional_weighted_avg_clv_pct` descending (primary), then
  `notional_weighted_beat_close_rate` descending (secondary), then segment_key ascending (tie-break).
- When `notional_weighted_avg_clv_pct_weight_used == 0`, uses count-weighted `avg_clv_pct` as
  primary rank signal; `denominators.weighting` is set to `"count"`.
- Top 2-5 candidates emitted (default top_n=5).

## Artifact Schema

See `docs/features/FEATURE-hypothesis-ready-aggregations.md` for segment metric definitions.

Envelope:
- generated_at, run_id, user_slug, wallet, candidates[]

Each candidate:
- segment_key (e.g. "entry_price_tier:coinflip")
- rank (1-based)
- metrics (notional_weighted_avg_clv_pct, notional_weighted_beat_close_rate, avg_clv_pct,
  beat_close_rate, avg_entry_drift_pct, avg_minutes_to_close, median_minutes_to_close, win_rate, count,
  plus weight_used and count_used denominators for each)
- denominators (count_used, weight_used, weighting)
- falsification_plan (min_sample_size, min_coverage_rate, stop_conditions)

## Manifest Registration

`run_manifest.output_paths["hypothesis_candidates_json"]` contains the POSIX path.

## Files Changed

- `polytool/reports/coverage.py`: _build_hypothesis_candidates, write_hypothesis_candidates, _render_hypothesis_candidates
- `tools/cli/scan.py`: writes artifact, registers in output_paths and emitted
- `tests/test_coverage_report.py`: TestBuildHypothesisCandidates (6 tests)
- `tests/test_scan_trust_artifacts.py`: manifest path assertions

## Guardrails

- Offline only: no network calls, no backtesting engine, no unverifiable claims.
- All metrics come from already-computed segment_analysis; no new data access.
- Falsification plan values are static defaults, not model predictions.

## How to Verify

pytest -q
# All tests pass

# After a real scan:
# hypothesis_candidates.json appears in the run root directory
