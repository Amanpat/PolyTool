---
phase: quick-5
plan: "01"
subsystem: scan-pipeline
tags:
  - notional-weighting
  - coverage-report
  - debug-artifact
  - scan
dependency_graph:
  requires:
    - polytool/reports/coverage.py (extract_position_notional_usd)
    - tools/cli/scan.py (_run_scan_pipeline)
  provides:
    - _normalize_position_notional (scan.py)
    - _build_notional_weight_debug (scan.py)
    - notional_weight_debug.json (run artifact)
  affects:
    - coverage_reconciliation_report.md (Top Segments now populated)
    - run_manifest.output_paths (new notional_weight_debug_json key)
tech_stack:
  added: []
  patterns:
    - in-place mutation of positions list before report build
    - debug artifact pattern (same as resolution_parity_debug.json)
key_files:
  created: []
  modified:
    - tools/cli/scan.py
    - tests/test_coverage_report.py
    - docs/features/FEATURE-hypothesis-ready-aggregations.md
decisions:
  - Normalize position_notional_usd in scan.py (not coverage.py) so the field
    is canonical on the dict before build_coverage_report reads it
  - Debug artifact written unconditionally per run (not conditional on missing data)
  - notional_weight_debug_json added to both output_paths and emitted dicts
metrics:
  duration: "~15 minutes"
  completed: "2026-02-20T21:14:20Z"
  tasks_completed: 3
  files_modified: 3
---

# Quick Task 5: Fix Notional-Weighted Metrics Null by Normalizing position_notional_usd in scan.py

**One-liner:** Inject canonical `position_notional_usd` from `total_cost` fallback in scan pipeline before `build_coverage_report`, and emit `notional_weight_debug.json` to the run root.

## Objective

Fix notional-weighted segment metrics (`notional_weight_total_global=0`, Top Segments `None`) by
normalizing `position_notional_usd` onto each position dict before `build_coverage_report` is
called. Real dossier positions carry `total_cost`, not `position_notional_usd`, so the fallback
chain inside `coverage.py` never fires — the field is absent at read time.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Inject position_notional_usd + emit notional_weight_debug.json | 1e47f3a | tools/cli/scan.py |
| 2 | Add unit tests for notional normalization + string coercion | 501addd | tests/test_coverage_report.py |
| 3 | Add Notional Parity Guarantee note to feature doc | b592d94 | docs/features/FEATURE-hypothesis-ready-aggregations.md |

## What Was Built

### Task 1 — scan.py changes

Added two private helpers to `tools/cli/scan.py`:

- `_normalize_position_notional(positions)`: iterates positions in-place, skips any with a valid
  `position_notional_usd`, calls `extract_position_notional_usd(pos)` for the rest, writes result
  back onto the dict
- `_build_notional_weight_debug(positions)`: builds a JSON-serialisable payload from
  already-normalized positions: totals, missing count, reason breakdown (NO_FIELDS, NON_NUMERIC,
  ZERO_OR_NEGATIVE, FALLBACK_FAILED), and 10-position sample

In `_run_scan_pipeline`, before the `build_coverage_report(...)` call:
```python
_normalize_position_notional(positions)
notional_debug = _build_notional_weight_debug(positions)
```

After `parity_debug_path.write_text(...)`:
```python
notional_debug_path = output_dir / "notional_weight_debug.json"
notional_debug_path.write_text(json.dumps(notional_debug, indent=2, sort_keys=True), encoding="utf-8")
```

Both `output_paths` and `emitted` dicts gain `"notional_weight_debug_json": notional_debug_path.as_posix()`.

### Task 2 — new tests

Added `TestExtractPositionNotionalUsd` (2 tests) and `TestNotionalWeightInCoverageReport` (2 tests)
to `tests/test_coverage_report.py`. Total coverage test count: 120 (was 116).

### Task 3 — feature doc

Appended "Notional Parity Guarantee" section to
`docs/features/FEATURE-hypothesis-ready-aggregations.md` documenting the normalization priority
chain and the `notional_weight_debug.json` artifact schema.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `wallet` missing from `build_coverage_report` test calls**
- **Found during:** Task 2 test run
- **Issue:** Plan's test code called `build_coverage_report(positions=..., run_id=..., user_slug=...)` without the required `wallet` positional argument
- **Fix:** Added `wallet="0xabc"` / `wallet="0xdef"` to the two test calls
- **Files modified:** tests/test_coverage_report.py
- **Commit:** 501addd

**2. [Rule 1 - Bug] `hypothesis_meta` looked up at wrong report key**
- **Found during:** Task 2 test run
- **Issue:** Plan's test accessed `report.get("hypothesis_meta", {})` but `hypothesis_meta` lives at `report["segment_analysis"]["hypothesis_meta"]`
- **Fix:** Changed lookup to `report.get("segment_analysis", {}).get("hypothesis_meta", {})`
- **Files modified:** tests/test_coverage_report.py
- **Commit:** 501addd

## Verification

```
python -m pytest tests/test_coverage_report.py -v --tb=short   # 120 passed
python -m pytest tests/test_scan_trust_artifacts.py -v --tb=short  # 27 passed
python -m pytest -v --tb=short  # 446 passed
grep "notional_weight_debug_json" tools/cli/scan.py  # appears in output_paths + emitted
grep "_normalize_position_notional" tools/cli/scan.py  # called before build_coverage_report
```

## Self-Check: PASSED

All files exist and all commits are present in git history.
