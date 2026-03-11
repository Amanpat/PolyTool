---
phase: quick-11
plan: 01
subsystem: docs
tags: [simtrader, documentation, clean, diff, activeness-probe]

# Dependency graph
requires: []
provides:
  - README_SIMTRADER.md documents simtrader clean (dry-run default, safety notes, category flags)
  - README_SIMTRADER.md documents simtrader diff (--a/--b flags, stdout output, disk output at diffs/)
  - CURRENT_STATE.md SimTrader section lists activeness probe, clean, and diff as shipped
  - SPEC-0010 Implementation Status lists probe, clean, diff under Shipped; Next is accurate
  - FEATURE doc What shipped covers probe, clean, diff; Next steps no longer lists stale items
affects: [simtrader, docs]

# Tech tracking
tech-stack:
  added: []
  patterns: []

key-files:
  created: []
  modified:
    - docs/README_SIMTRADER.md
    - docs/CURRENT_STATE.md
    - docs/features/FEATURE-simtrader-replay-shadow-ui.md
    - docs/specs/SPEC-0010-simtrader-vision-and-roadmap.md

key-decisions:
  - "SPEC-0010 Implementation Status is treated as a living header (not a frozen spec body) and updated on each delivery — consistent with prior updates"
  - "clean and diff placed after 'Local UI: report and browse' section in README_SIMTRADER.md, before Artifacts layout"
  - "Activeness probe also removed from README_SIMTRADER.md Next engineering targets since it shipped in quick-10"

patterns-established:
  - "Shipped features must be removed from 'Next steps' sections in all doc files simultaneously to avoid doc drift"

# Metrics
duration: 2min
completed: 2026-02-25
---

# Quick-11: Sync Public Docs with Current SimTrader Summary

**Four doc files updated to reflect activeness probe, simtrader clean, and simtrader diff as shipped — removing stale "next steps" entries and adding clean/diff usage sections with safety notes and output locations.**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-02-25T23:30:32Z
- **Completed:** 2026-02-25T23:32:25Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Added `clean` and `diff` rows to the subcommand table in README_SIMTRADER.md
- Added "Artifact cleanup: clean" section with dry-run default, `--yes` flag, category flags (`--runs`, `--tapes`, `--sweeps`, `--batches`, `--shadow`), and three safety notes
- Added "Comparing runs: diff" section with `--a`/`--b` syntax, stdout output description, `artifacts/simtrader/diffs/` disk output, and `--output-dir` flag
- Removed stale "next steps" lines for activeness probe, clean, and diff from README_SIMTRADER.md, FEATURE doc, and SPEC-0010
- Updated CURRENT_STATE.md SimTrader bullet list with activeness probe and artifact management entries
- Updated FEATURE doc to add "Activeness probe" and "Artifact management" subsections under "What shipped"
- Updated SPEC-0010 Implementation Status: added probe and artifact management to Shipped, removed probe from Next

## Task Commits

Each task was committed atomically:

1. **Task 1: Add simtrader clean and diff sections to README_SIMTRADER.md** - `2642b08` (docs)
2. **Task 2: Update CURRENT_STATE.md, FEATURE doc, and SPEC-0010 Implementation Status** - `7de79c4` (docs)

**Plan metadata:** (see final commit below)

## Files Created/Modified

- `docs/README_SIMTRADER.md` - Added clean/diff to subcommand table; added "Artifact cleanup: clean" and "Comparing runs: diff" sections; removed stale next-steps lines
- `docs/CURRENT_STATE.md` - Added activeness probe and artifact management bullets to SimTrader "What exists today" list
- `docs/features/FEATURE-simtrader-replay-shadow-ui.md` - Added "Activeness probe" and "Artifact management" subsections under What shipped; replaced Next steps with unshipped items only
- `docs/specs/SPEC-0010-simtrader-vision-and-roadmap.md` - Added probe and artifact management to Shipped list; removed probe from Next

## Decisions Made

- SPEC-0010 Implementation Status is treated as a living header updated on each delivery, consistent with prior updates (shadow mode was last addition on same date 2026-02-25).
- Activeness probe removed from README_SIMTRADER.md "Next engineering targets" as well, since it shipped in quick-10.
- clean and diff sections placed between "Local UI" and "Artifacts layout" sections — logical location after the UI section and before the reference layout.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- All four doc files are now consistent with shipped state as of 2026-02-25
- Only genuinely unshipped items remain in "Next steps" / "Next engineering targets" sections across all docs
- No blockers

## Self-Check

### Files exist

- `docs/README_SIMTRADER.md` — present (modified)
- `docs/CURRENT_STATE.md` — present (modified)
- `docs/features/FEATURE-simtrader-replay-shadow-ui.md` — present (modified)
- `docs/specs/SPEC-0010-simtrader-vision-and-roadmap.md` — present (modified)

### Commits exist

- `2642b08` — Task 1 (README_SIMTRADER.md)
- `7de79c4` — Task 2 (CURRENT_STATE, FEATURE, SPEC-0010)

## Self-Check: PASSED

---
*Phase: quick-11*
*Completed: 2026-02-25*
