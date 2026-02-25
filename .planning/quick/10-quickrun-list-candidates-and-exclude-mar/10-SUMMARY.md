---
phase: 10-quickrun-list-candidates-and-exclude-mar
plan: 01
subsystem: cli
tags: [simtrader, quickrun, market_picker, argparse, offline-tests]

# Dependency graph
requires:
  - phase: simtrader-quickrun
    provides: quickrun CLI handler and MarketPicker.auto_pick/auto_pick_many
provides:
  - --list-candidates N flag: print top N passing candidates with book stats then exit
  - --exclude-market SLUG flag (repeatable): skip slugs during auto-pick
  - excluded_slugs and list_candidates in quickrun_context manifest persistence
  - auto_pick() exclude_slugs forwarding to auto_pick_many()
affects:
  - quickrun users who want candidate visibility and exclusion control

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "list-candidates early-exit path in _quickrun() before the normal resolve/record path"
    - "exclude_slugs forwarded from CLI args through auto_pick() to auto_pick_many()"
    - "quickrun_context dict extended with operational metadata (excluded_slugs, list_candidates)"

key-files:
  created: []
  modified:
    - tools/cli/simtrader.py
    - packages/polymarket/simtrader/market_picker.py
    - tests/test_simtrader_quickrun.py
    - docs/README_SIMTRADER.md

key-decisions:
  - "list-candidates mode exits before normal resolve/record flow; --market + --list-candidates emits a warning and falls through to normal flow"
  - "excluded_slugs persisted as list (not set) in quickrun_context for JSON serializability"
  - "validate_book called again per candidate in list-candidates mode to get depth stats for display"

patterns-established:
  - "Pattern: use getattr(args, 'field', default) for optional args that may not exist on all code paths"

# Metrics
duration: 4min
completed: 2026-02-25
---

# Quick Task 10: --list-candidates and --exclude-market for quickrun

**quickrun gets candidate pool visibility (--list-candidates N) and slug exclusion (--exclude-market SLUG) to break the always-same-market loop**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-02-25T20:36:32Z
- **Completed:** 2026-02-25T20:40:34Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- Added `--list-candidates N` to quickrun: prints top N passing candidates (slug, question, YES/NO bid/ask/depth) and exits 0 without recording
- Added `--exclude-market SLUG` (repeatable) to quickrun: passes excluded slugs to `auto_pick`/`auto_pick_many` so those markets are skipped
- Extended `auto_pick()` in `market_picker.py` with `exclude_slugs` parameter forwarded to `auto_pick_many()`
- Added `excluded_slugs` and `list_candidates` keys to `quickrun_context` for auditability in manifests
- 9 new offline tests (TestListCandidates x6, TestExcludeMarket x3); total 56 -> 65 tests all passing
- README flags table updated + new "Browsing candidates and excluding over-represented markets" subsection

## Task Commits

1. **Task 1: Add --list-candidates and --exclude-market to quickrun CLI** - `ce9a50f` (feat)
2. **Task 2: Offline tests for list-candidates and exclude-market** - `d3b9a75` (test)
3. **Task 3: Document new flags in README_SIMTRADER.md** - `b95f20b` (docs)

**Plan metadata:** (see final commit below)

## Files Created/Modified

- `tools/cli/simtrader.py` - Added `--list-candidates`/`--exclude-market` argparse args, list-candidates early-exit path in `_quickrun()`, exclude_slugs forwarding in `auto_pick()` call, `excluded_slugs`/`list_candidates` in `quickrun_context`
- `packages/polymarket/simtrader/market_picker.py` - Added `exclude_slugs: Optional[set] = None` parameter to `auto_pick()` with forwarding to `auto_pick_many()`
- `tests/test_simtrader_quickrun.py` - `TestListCandidates` (6 tests) and `TestExcludeMarket` (3 tests) added; helper functions `_make_resolved_market()` and `_patch_quickrun_externals()` added
- `docs/README_SIMTRADER.md` - Two rows added to flags table; new subsection with bash examples

## Decisions Made

- `--list-candidates` with `--market` explicitly set: emits warning to stderr and falls through to normal dry-run/run flow (does not error out)
- `excluded_slugs` persisted as `list(set)` in `quickrun_context` (JSON-serializable, deterministic order not guaranteed but functional)
- In list-candidates mode, `validate_book` is called again per candidate to get `depth_total` for display (minor extra network in live use, but needed for stats)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Both flags are live and tested; users can immediately use `--dry-run --list-candidates 5` to inspect the candidate pool
- `--exclude-market` is repeatable and persists to manifests for traceability
- No blockers

## Self-Check: PASSED

Files verified:
- `tools/cli/simtrader.py` - exists, contains `list_candidates`
- `packages/polymarket/simtrader/market_picker.py` - exists, `auto_pick` has `exclude_slugs` param
- `tests/test_simtrader_quickrun.py` - exists, contains `TestListCandidates` and `TestExcludeMarket`
- `docs/README_SIMTRADER.md` - exists, contains `exclude-market` in flags table and new subsection

Commits verified:
- `ce9a50f` - feat: add --list-candidates and --exclude-market to quickrun CLI
- `d3b9a75` - test: offline tests for new flags
- `b95f20b` - docs: README_SIMTRADER.md updated

---
*Phase: 10-quickrun-list-candidates-and-exclude-mar*
*Completed: 2026-02-25*
