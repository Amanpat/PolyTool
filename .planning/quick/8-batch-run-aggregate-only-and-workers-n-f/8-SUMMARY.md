---
phase: quick-8
plan: 01
subsystem: cli
tags: [batch-run, hypothesis-leaderboard, parallel, concurrent.futures, ThreadPoolExecutor]

requires: []
provides:
  - "--aggregate-only + --run-roots mode: re-aggregate leaderboard from existing run roots without re-scanning"
  - "_resolve_run_roots() helper: directory->subdirs or file->line-per-path resolution"
  - "aggregate_from_roots() function: read user_slug from hypothesis_candidates.json, build per_user + segment_contributions"
  - "aggregate_only() entry-point: wraps BatchRunner with run_roots_override for clean main() path"
  - "--workers N parallelism: ThreadPoolExecutor with futures collected in original user order"
  - "continue_on_error respected under parallel execution: failures recorded, run continues"
affects: [batch-run usage, leaderboard re-generation workflows]

tech-stack:
  added: [concurrent.futures (stdlib, ThreadPoolExecutor)]
  patterns:
    - "run_roots_override kwarg on run_batch() bypasses scan loop without changing aggregation logic"
    - "futures collected in submission order (zip(users, futures)) guarantees deterministic output"
    - "aggregate_only() as thin entry-point delegates to BatchRunner for DRY aggregation path"

key-files:
  created: []
  modified:
    - tools/cli/batch_run.py
    - tests/test_batch_run.py
    - docs/features/FEATURE-batch-run-hypothesis-leaderboard.md

key-decisions:
  - "Collect parallel futures in original user-list order (zip(users, futures)) not completion order - guarantees byte-identical ordering vs serial"
  - "aggregate_from_roots() reads user_slug from hypothesis_candidates.json, falls back to directory name - handles both auto-named and custom run roots"
  - "run_roots_override=None (not a flag) on run_batch() keeps interface clean; aggregate_only() is the public entry point"
  - "--users changed from required=True to required=False; guarded in main() with explicit error message when not --aggregate-only"

patterns-established:
  - "Injectable override pattern: run_roots_override kwarg on BatchRunner.run_batch() lets aggregate-only bypass scan loop while reusing all aggregation code"
  - "Deterministic parallel collection: always iterate futures in submission order, never in completion order"

duration: 5min
completed: 2026-02-20
---

# Quick-8: Batch-Run Aggregate-Only and Workers Summary

**`--aggregate-only --run-roots` for instant leaderboard re-generation from existing run roots, plus `--workers N` parallel scans via ThreadPoolExecutor with deterministic output ordering**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-20T23:44:01Z
- **Completed:** 2026-02-20T23:49:05Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Added `_resolve_run_roots()`: accepts a directory (immediate subdirs) or a text file (line-per-path), raises `FileNotFoundError` on missing dirs
- Added `aggregate_from_roots()` + `aggregate_only()`: re-aggregate leaderboard from existing run roots with no scan invocations; user slug read from `hypothesis_candidates.json`
- Added `workers` param to `BatchRunner.run_batch()`: `ThreadPoolExecutor` when `workers > 1`, collecting futures in original user order for determinism; `continue_on_error` respected
- Added `--aggregate-only`, `--run-roots`, `--workers` args to parser; `--users` made optional with explicit guard
- 5 new tests (aggregate-only directory, file, full flow; workers ordering; workers continue-on-error) - all 11 tests pass

## Task Commits

1. **Task 1: Add --aggregate-only + --run-roots and --workers to BatchRunner** - `d672fc3` (feat)
2. **Task 2: Tests for aggregate-only and workers determinism + update feature doc** - `a81e1ef` (feat)

**Plan metadata:** (docs commit below)

## Files Created/Modified

- `tools/cli/batch_run.py` - Added `_resolve_run_roots`, `aggregate_from_roots`, `aggregate_only`, `run_roots_override` param, `workers` param, updated parser and main()
- `tests/test_batch_run.py` - Added 5 new test functions (11 total, up from 6), imported `_resolve_run_roots` and `aggregate_only`
- `docs/features/FEATURE-batch-run-hypothesis-leaderboard.md` - Added Aggregate-Only Mode and Parallel Scan Workers sections; updated batch options list and Tests section

## Decisions Made

- Used `zip(users, futures)` to collect parallel results in submission order, not completion order - guaranteed determinism without sorting
- `aggregate_from_roots()` reads `user_slug` from `hypothesis_candidates.json` with fallback to directory name - handles both auto-named and custom run roots gracefully
- `aggregate_only()` constructs a `BatchRunner` internally and calls `run_batch(run_roots_override=...)` to avoid duplicating aggregation logic
- `--users` changed to `required=False` in argparse; explicit guard in `main()` prints a clear error - cleaner than argparse group logic

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `--aggregate-only` and `--workers` are production-ready with full test coverage
- Feature doc updated with usage examples, option descriptions, and test function list

## Self-Check: PASSED

- `tools/cli/batch_run.py` exists: FOUND
- `tests/test_batch_run.py` exists: FOUND
- `docs/features/FEATURE-batch-run-hypothesis-leaderboard.md` exists: FOUND
- Commit `d672fc3` exists: FOUND
- Commit `a81e1ef` exists: FOUND
- All 11 tests pass: CONFIRMED

---
*Phase: quick-8*
*Completed: 2026-02-20*
