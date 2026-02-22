---
phase: quick
plan: 4
subsystem: coverage-reports
tags: [hypothesis, candidates, artifacts, scan, segment-analysis]
dependency_graph:
  requires: [segment_analysis (from coverage.py _build_segment_analysis)]
  provides: [hypothesis_candidates.json, run_manifest.output_paths.hypothesis_candidates_json]
  affects: [polytool/reports/coverage.py, tools/cli/scan.py]
tech_stack:
  added: []
  patterns: [envelope JSON, deterministic ranking, falsification plan schema]
key_files:
  created:
    - docs/features/FEATURE-hypothesis-candidates.md
  modified:
    - polytool/reports/coverage.py
    - tools/cli/scan.py
    - tests/test_coverage_report.py
    - tests/test_scan_trust_artifacts.py
decisions:
  - Weighting falls back to count-weighted avg_clv_pct when notional weight is 0; denominators.weighting set to "count"
  - Falsification plan uses static defaults (not model predictions) — offline-safe
  - Sort key: notional_weighted_avg_clv_pct desc, notional_weighted_beat_close_rate desc, segment_key asc (deterministic)
metrics:
  duration: ~15 minutes
  completed: 2026-02-20
  tasks_completed: 2
  files_changed: 4
  files_created: 1
---

# Quick Task 4: Build Hypothesis Candidates JSON Artifact

## One-Liner

hypothesis_candidates.json artifact with ranked segments, metrics snapshot, explicit denominators, and falsification plan wired into scan output and coverage markdown.

## What Was Built

### Task 1: coverage.py additions

Three functions added to `polytool/reports/coverage.py`:

**`_build_hypothesis_candidates(segment_analysis, top_n=5)`**
- Iterates across all five standard dimensions (entry_price_tier, market_type, league, sport, category)
- Filters to segments with count >= TOP_SEGMENT_MIN_COUNT (5)
- Requires non-None notional_weighted_avg_clv_pct (or count-weighted fallback when weight is 0)
- Sorts: notional_weighted_avg_clv_pct desc, notional_weighted_beat_close_rate desc, segment_key asc
- Returns list of candidate dicts with segment_key, rank, metrics, denominators, falsification_plan

**`write_hypothesis_candidates(candidates, output_dir, generated_at, run_id, user_slug, wallet)`**
- Wraps candidates in envelope with metadata
- Writes to `output_dir/hypothesis_candidates.json` (indent=2, sort_keys=True, allow_nan=False)
- Returns POSIX path string

**`_render_hypothesis_candidates(report)`**
- Markdown section `## Hypothesis Candidates`
- Summary table: Rank | Segment | Count | Notional-Wt CLV% | Notional-Wt Beat-Close | Weighting | Min Sample
- Per-candidate subsection with falsification plan bullets

Wired into:
- `build_coverage_report`: calls `_build_hypothesis_candidates` after `_build_segment_analysis`, adds `hypothesis_candidates` key to report dict
- `_render_markdown`: calls `_render_hypothesis_candidates` after `_render_hypothesis_signals`

### Task 2: scan.py, tests, feature doc

**scan.py**
- Added `write_hypothesis_candidates` to import block
- Added call to `write_hypothesis_candidates` immediately after `write_coverage_report`
- Added `hypothesis_candidates_json` to `output_paths` dict and `emitted` dict

**tests/test_coverage_report.py**
- Added imports: `_build_hypothesis_candidates`, `write_hypothesis_candidates`
- Added `TestBuildHypothesisCandidates` class with 6 tests:
  1. `test_empty_segment_analysis_returns_empty_list`
  2. `test_candidates_below_min_count_excluded`
  3. `test_candidates_ranked_by_notional_clv_desc`
  4. `test_candidate_has_required_fields`
  5. `test_write_hypothesis_candidates_produces_valid_json`
  6. `test_build_coverage_report_includes_hypothesis_candidates_key`

**tests/test_scan_trust_artifacts.py**
- Added 3 assertions after existing segment_analysis_json assertion:
  - `assert "hypothesis_candidates_json" in manifest["output_paths"]`
  - `assert "hypothesis_candidates_json" in emitted`
  - `assert Path(emitted["hypothesis_candidates_json"]).exists()`

**docs/features/FEATURE-hypothesis-candidates.md**
- New feature doc: candidate selection rules, artifact schema, manifest registration, guardrails, verification steps

## Decisions Made

1. **Count-weighted fallback**: When `notional_weighted_avg_clv_pct_weight_used == 0`, uses `avg_clv_pct` as rank signal and sets `denominators.weighting = "count"`. Ensures segments with missing notional data can still surface if they have count-weighted CLV.

2. **Static falsification defaults**: `min_sample_size = max(30, count * 2)`, `min_coverage_rate = 0.80`, stop_conditions are hardcoded strings. These are guidance values, not model predictions — keeps the artifact offline-safe.

3. **Sort determinism**: Three-level sort (CLV desc, beat_close_rate desc, segment_key asc) ensures identical output for identical input regardless of dict iteration order.

## Commits

| Task | Commit | Description |
| ---- | ------ | ----------- |
| 1 | 43fc868 | feat(quick-4): add _build_hypothesis_candidates, write_hypothesis_candidates, _render_hypothesis_candidates |
| 2 | 4dc721f | feat(quick-4): wire hypothesis_candidates into scan.py, add tests and feature doc |

## Test Results

- 442 passed, 0 failed (full suite)
- 6 new tests in TestBuildHypothesisCandidates all pass
- 3 new assertions in test_scan_trust_artifacts pass

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- `polytool/reports/coverage.py`: modified with _build_hypothesis_candidates, write_hypothesis_candidates, _render_hypothesis_candidates
- `tools/cli/scan.py`: modified with import and call wiring
- `tests/test_coverage_report.py`: 6 new tests in TestBuildHypothesisCandidates
- `tests/test_scan_trust_artifacts.py`: 3 new assertions
- `docs/features/FEATURE-hypothesis-candidates.md`: created
- Commits 43fc868 and 4dc721f verified in git log
- 442 tests pass (no new failures)
