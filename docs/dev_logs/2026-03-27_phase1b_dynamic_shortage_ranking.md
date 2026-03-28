# Phase 1B: Dynamic Shortage Ranking for Candidate Discovery

**Date:** 2026-03-27
**Task:** quick-033
**Branch:** phase-1B

## Summary

Replaced the two hardcoded Phase 1B shortage dicts in `candidate_discovery.py`
and `simtrader.py` with a live-loading function `load_live_shortage()` that reads
current corpus shortage from tape directories via `capture_status.compute_status()`.
Previously, after each tape capture batch the operator had to manually update two
copies of the same shortage dict. Now `quickrun --list-candidates` automatically
reflects the current shortage state, and the CLI output includes a
`[shortage] source : ...` line so the operator knows whether live or fallback data
was used.

## Files Changed

- `packages/polymarket/simtrader/candidate_discovery.py` — added `load_live_shortage()`
  function; updated module docstring exports list
- `tools/cli/simtrader.py` — replaced hardcoded `_DEFAULT_SHORTAGE` dict and static
  `CandidateDiscovery(picker, shortage=_DEFAULT_SHORTAGE)` call with
  `load_live_shortage()` call; added `[shortage] source` line to CLI output
- `tests/test_simtrader_candidate_discovery.py` — added `TestLoadLiveShortage` class
  with 5 offline tests covering all paths

## Previous Behavior

Two identical hardcoded shortage dicts existed:

1. `_DEFAULT_SHORTAGE` in `candidate_discovery.py` (module-level constant)
2. `_DEFAULT_SHORTAGE` local dict in `tools/cli/simtrader.py` inside the
   `--list-candidates` block (lines 1613-1621)

Both read:
```python
{"sports": 15, "politics": 9, "crypto": 10, "new_market": 5, "near_resolution": 1, "other": 0}
```

After every tape capture batch, the operator had to manually edit `simtrader.py`
to keep the shortage values current. This was error-prone and easy to forget.

## New Live-Shortage Behavior

`load_live_shortage(tape_roots=None)` is now exported from `candidate_discovery.py`.
It:

1. Imports `compute_status` from `tools.gates.capture_status` inside the function
   body (guarded by `try/except ImportError`) to avoid a hard dependency at module
   import time.
2. Builds the tape root paths the same way `capture_status.main()` does — using
   `DEFAULT_TAPE_ROOTS` resolved against `_REPO_ROOT`.
3. Calls `compute_status(resolved_roots)` and extracts per-bucket `need` values.
4. Returns `(shortage_dict, source_label)` where `source_label` is one of:
   - `"live (N tapes scanned)"` — compute_status ran and found tapes
   - `"fallback (no tapes found)"` — compute_status ran but found 0 tapes
   - `"fallback (import error)"` — capture_status module unavailable
   - `"fallback (read error: ...)"` — unexpected exception during scan

The `shortage_dict` always covers all 6 buckets including `"other"` (always 0).

## Fallback Behavior

The fallback to `_DEFAULT_SHORTAGE` triggers when:

- `tools.gates.capture_status` cannot be imported (CI, partial install, etc.)
- `compute_status` raises any exception (disk error, permission denied, etc.)
- The corpus is empty: `total_have == 0` and `total_need == 0`

Default fallback values used:
```python
{"sports": 15, "politics": 9, "crypto": 10, "new_market": 5, "near_resolution": 1, "other": 0}
```

These match the corpus shortage as of 2026-03-27.

## Commands Run

```
python -m pytest tests/test_simtrader_candidate_discovery.py -q -x --tb=short
# Result: 32 passed in 0.30s

python -m pytest tests/ -q --tb=short
# Result: 2717 passed, 25 warnings in 76.80s
```

## Example Output

Running `python -m polytool simtrader quickrun --list-candidates 3` now produces:

```
[candidate 1] slug     : will-btc-exceed-100k-march
[candidate 1] question : Will BTC exceed $100K by end of March?
[candidate 1] bucket   : crypto
[candidate 1] score    : 0.82
[candidate 1] why      : bucket=crypto shortage=10 score=0.82 depth=145 probe=active
[candidate 1] depth    : YES=145.0  NO=132.0
[candidate 1] probe    : 2/2 active, 48 updates
[candidate 2] slug     : nfl-championship-winner
...
[shortage] source : live (10 tapes scanned)
Listed 3 candidates.
```

In a CI environment (no tape directories):
```
[shortage] source : fallback (no tapes found)
Listed 3 candidates.
```

## Test Results

```
32 passed, 0 failed, 0 skipped  (tests/test_simtrader_candidate_discovery.py)
2717 passed, 0 failed, 25 warnings  (full test suite)
```

New tests in `TestLoadLiveShortage`:
1. `test_live_path_returns_live_label_and_correct_dict` — mocked compute_status with 10 tapes
2. `test_fallback_no_tapes_found` — empty corpus (total_have=0, total_need=0)
3. `test_fallback_import_error` — blocked module import via sys.modules
4. `test_fallback_read_error` — compute_status raises RuntimeError
5. `test_shortage_ranking_changes_with_shortage_value` — score_for_capture ordering validation
