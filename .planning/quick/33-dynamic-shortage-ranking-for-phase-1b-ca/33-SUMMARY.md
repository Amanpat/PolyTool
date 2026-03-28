---
phase: quick-033
plan: 01
subsystem: simtrader/candidate-discovery
tags: [candidate-discovery, corpus, shortage, phase-1b, cli]
dependency_graph:
  requires: [capture_status.compute_status, corpus_audit.DEFAULT_TAPE_ROOTS]
  provides: [load_live_shortage, live shortage wiring in --list-candidates]
  affects: [quickrun --list-candidates output, CandidateDiscovery scoring]
tech_stack:
  added: []
  patterns: [guarded-import, fallback-with-label, tuple-return]
key_files:
  created:
    - docs/dev_logs/2026-03-27_phase1b_dynamic_shortage_ranking.md
  modified:
    - packages/polymarket/simtrader/candidate_discovery.py
    - tools/cli/simtrader.py
    - tests/test_simtrader_candidate_discovery.py
decisions:
  - "Import capture_status inside load_live_shortage() body to avoid hard module-level dependency"
  - "Return (dict, str) tuple so callers can log the source without extra calls"
  - "BUCKET_OTHER always forced to 0 in live path — not a corpus bucket"
  - "total_have==0 AND total_need==0 triggers no-tapes fallback (not an error condition)"
metrics:
  duration: "~15 minutes"
  completed: "2026-03-28"
  tasks_completed: 3
  files_modified: 4
---

# Phase quick-033 Plan 01: Dynamic Shortage Ranking for Phase 1B Candidate Discovery Summary

**One-liner:** Live corpus shortage loader via capture_status.compute_status() replaces hardcoded dicts in candidate discovery, with 4-case fallback and source label in CLI output.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add load_live_shortage() and wire CLI | 9456edb | candidate_discovery.py, simtrader.py |
| 2 | Add TestLoadLiveShortage (5 TDD tests) | 7e600af | tests/test_simtrader_candidate_discovery.py |
| 3 | Full regression + dev log | 759dc9f | docs/dev_logs/2026-03-27_phase1b_dynamic_shortage_ranking.md |

## What Was Built

### load_live_shortage()

New exported function in `packages/polymarket/simtrader/candidate_discovery.py`:

- Imports `compute_status` and `DEFAULT_TAPE_ROOTS` inside the function body (guarded `try/except ImportError`) so the module has no hard dependency on `tools.gates` at import time.
- Resolves tape roots the same way `capture_status.main()` does: relative paths resolved against `_REPO_ROOT`.
- Returns `(shortage_dict, source_label)` with 4 cases:
  - `"live (N tapes scanned)"` — live read succeeded
  - `"fallback (no tapes found)"` — total_have==0 and total_need==0
  - `"fallback (import error)"` — capture_status module unavailable
  - `"fallback (read error: ...)"` — unexpected exception

### simtrader.py --list-candidates

- Removed the hardcoded `_DEFAULT_SHORTAGE` local dict (7 lines)
- Replaced with `load_live_shortage()` call
- Added `print(f"[shortage] source : {_shortage_source}")` line before "Listed N candidates."

### Tests

`TestLoadLiveShortage` in `tests/test_simtrader_candidate_discovery.py` — 5 offline tests:

1. Live path: mocked `compute_status` with 10 tapes; asserts label and dict values
2. No-tapes fallback: total_have=0, total_need=0; asserts `_DEFAULT_SHORTAGE` returned
3. Import error: blocks `sys.modules` entries; asserts "import error" in label
4. Read error: `compute_status` raises `RuntimeError`; asserts "read error" in label
5. Ranking change: `score_for_capture` with high vs zero shortage; asserts ordering

## Test Results

```
32 passed, 0 failed  (tests/test_simtrader_candidate_discovery.py)
2717 passed, 0 failed, 25 warnings  (full suite)
```

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None.

## Self-Check: PASSED

- `packages/polymarket/simtrader/candidate_discovery.py` — FOUND (contains load_live_shortage)
- `tools/cli/simtrader.py` — FOUND (no _DEFAULT_SHORTAGE dict, has _shortage_source)
- `tests/test_simtrader_candidate_discovery.py` — FOUND (TestLoadLiveShortage with 5 tests)
- `docs/dev_logs/2026-03-27_phase1b_dynamic_shortage_ranking.md` — FOUND
- Commit 9456edb — FOUND
- Commit 7e600af — FOUND
- Commit 759dc9f — FOUND
