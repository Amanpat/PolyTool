---
phase: quick-7
plan: "01"
subsystem: reports/segment-analysis
tags: [robust-stats, median, trimmed-mean, iqr, segment-buckets, leaderboard]
dependency_graph:
  requires: [quick-6]
  provides: [median_clv_pct, trimmed_mean_clv_pct, p25_clv_pct, p75_clv_pct, robust stats in leaderboard markdown]
  affects: [polytool/reports/coverage.py, tools/cli/batch_run.py, segment_analysis.json, hypothesis_candidates.json]
tech_stack:
  added: []
  patterns: [sort-based percentile computation, count-based trim, arrival-order capping]
key_files:
  created:
    - docs/features/FEATURE-robust-signal-stats.md
  modified:
    - polytool/reports/coverage.py
    - tools/cli/batch_run.py
    - tests/test_coverage_report.py
    - tests/test_batch_run.py
decisions:
  - "Use manual sort-based computation (no statistics stdlib) for zero-dependency robust stats"
  - "Nearest-rank percentile: sorted_vals[ceil(n * p) - 1] (0-indexed)"
  - "10% count-based trim: floor(n * 0.10) removed from each tail; n < 10 means no trim"
  - "Cap raw value lists at MAX_ROBUST_VALUES=500 using first-arrival order (deterministic)"
  - "beat_close is required positional arg in _accumulate_segment_bucket — tests must pass it explicitly"
metrics:
  duration_minutes: 15
  completed_date: "2026-02-20"
  tasks_completed: 2
  files_modified: 4
  files_created: 1
---

# Phase quick-7 Plan 01: Add Robust Segment Stats (Median, Trimmed Mean, IQR) Summary

**One-liner:** Sort-based median, 10%-trimmed mean, and nearest-rank p25/p75 added to every segment bucket for clv_pct and entry_drift_pct, with memory-capped raw value lists (MAX_ROBUST_VALUES=500) and leaderboard markdown exposure.

## Tasks Completed

| Task | Name | Commit | Files |
| --- | --- | --- | --- |
| 1 | Add robust stats accumulation and finalization in coverage.py | 6b5f791 | polytool/reports/coverage.py |
| 2 | Expose robust stats in leaderboard markdown and write tests + feature doc | 10f78c2 | tools/cli/batch_run.py, tests/test_coverage_report.py, tests/test_batch_run.py, docs/features/FEATURE-robust-signal-stats.md |

## What Was Built

### `_compute_robust_stats(values)` — `polytool/reports/coverage.py`
Pure-Python function computing median, 10% symmetric trimmed mean (count-based), p25, and p75 from a list. Returns a dict with all-None on empty input. No external dependencies.

### Segment bucket accumulation
`_empty_segment_bucket()` now initializes `_clv_pct_values` and `_entry_drift_pct_values` raw lists. `_accumulate_segment_bucket()` appends to these lists, capped at `MAX_ROBUST_VALUES=500`.

### Finalized bucket fields (10 new)
`_finalize_segment_bucket()` calls `_compute_robust_stats` on both lists and emits:
- `median_clv_pct`, `trimmed_mean_clv_pct`, `p25_clv_pct`, `p75_clv_pct`, `robust_clv_pct_count_used`
- `median_entry_drift_pct`, `trimmed_mean_entry_drift_pct`, `p25_entry_drift_pct`, `p75_entry_drift_pct`, `robust_entry_drift_pct_count_used`

### Hypothesis candidates propagation
`_build_hypothesis_candidates()` metrics_out dict now includes all 10 robust stat fields.

### Leaderboard markdown
`_build_markdown()` in `batch_run.py` pulls `median_clv_pct` and `trimmed_mean_clv_pct` from the first notional example's metrics and renders them in the Top Segment Detail section when non-None.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed missing `beat_close` positional argument in test calls**
- **Found during:** Task 2 test execution
- **Issue:** Plan's test code called `_accumulate_segment_bucket(b, "WIN", 0.0, 0.0, clv_pct=v)` but `beat_close` is a required positional argument (not optional) in the actual function signature
- **Fix:** Added `beat_close=None` to all test calls in `TestRobustStats.test_cap_deterministic`, `test_finalized_bucket_has_robust_fields`, and `test_deterministic_output_ordering`
- **Files modified:** `tests/test_coverage_report.py`
- **Commit:** 10f78c2

## Verification

All 474 tests pass (25 pre-existing deprecation warnings, 0 failures). New TestRobustStats class contributes 9 tests; `test_build_markdown_includes_robust_clv_stats` verifies leaderboard rendering.

## Self-Check: PASSED

Files verified present:
- polytool/reports/coverage.py — FOUND (contains `_compute_robust_stats`, `MAX_ROBUST_VALUES`, `median_clv_pct`)
- tools/cli/batch_run.py — FOUND (contains `median_clv_pct` in `_build_markdown`)
- tests/test_coverage_report.py — FOUND (contains `TestRobustStats`)
- tests/test_batch_run.py — FOUND (contains `test_build_markdown_includes_robust_clv_stats`)
- docs/features/FEATURE-robust-signal-stats.md — FOUND

Commits verified:
- 6b5f791 — FOUND (feat(quick-7): add robust stats to segment buckets)
- 10f78c2 — FOUND (feat(quick-7): expose robust stats in leaderboard markdown + tests + feature doc)
