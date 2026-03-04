---
phase: quick-17
plan: 17
subsystem: docs
tags: [readme, simtrader, studio, ui, user-guide]

# Dependency graph
requires: []
provides:
  - README.md SimTrader Studio user guide section with launch instructions, tab reference, workflows A/B/C, troubleshooting, and doc links
affects: [quick-12, quick-13, quick-14, quick-16]

# Tech tracking
tech-stack:
  added: []
  patterns: []

key-files:
  created: []
  modified:
    - README.md

key-decisions:
  - "Replaced old Studio UI stub (12 lines) with a 72-line full user guide in README.md"
  - "Used H3 subsections under H2 to keep README hierarchy consistent"
  - "Docker launch section uses docker compose up --build polytool (no script wrappers)"

patterns-established:
  - "Tab reference table as first orientation tool before workflows"
  - "Three canonical workflows (A/B/C) cover the shadow-to-replay learning loop"

# Metrics
duration: 2min
completed: 2026-03-04
---

# Quick-17: Update README.md with SimTrader Studio User Guide Summary

**Replaced the minimal Studio UI stub in README.md with a full user guide: launch (local + Docker), 8-tab reference, three click-by-click workflows, troubleshooting, and links to three deeper docs.**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-03-04T16:43:13Z
- **Completed:** 2026-03-04T16:44:52Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- Replaced 12-line "## Studio UI" stub with a 72-line "## SimTrader Studio (UI) — User Guide" section
- Added launch instructions for both local dev (`pip install polytool[studio]` + `--open`) and Docker (`docker compose up --build polytool`)
- Documented all 8 tabs in nav order (Dashboard, Sessions, Cockpit, Workspaces, Tapes, Reports, OnDemand, Settings)
- Added three numbered workflows (A: Shadow/Viewer/Rewind, B: OnDemand iterate, C: Cockpit artifact playback)
- Added troubleshooting covering 0-trades, no-tapes, WS-stall, and studio-won't-start
- Linked to three doc files: README_SIMTRADER.md, FEATURE-simtrader-studio.md, TODO_SIMTRADER_STUDIO.md

## Task Commits

1. **Task 1: Replace Studio UI stub with full user guide section in README.md** - `76b398e` (docs)

**Plan metadata:** see final commit below

## Files Created/Modified

- `README.md` — Replaced "## Studio UI" stub (lines 32-56) with "## SimTrader Studio (UI) — User Guide" section; 1 file changed, 60 insertions, 12 deletions

## Decisions Made

- Used H3 subsections (Launch, Tabs at a glance, Start here, Troubleshooting, Further reading) under H2 to match README's existing heading style
- Docker section uses `docker compose up --build polytool` rather than the legacy PowerShell/bash scripts (`studio_docker.ps1/sh`) which the old stub referenced
- Tab table follows actual HTML nav order: Dashboard → Sessions → Cockpit → Workspaces → Tapes → Reports → OnDemand → Settings

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

README.md now serves as a first-stop orientation for Studio users. The three doc links point to existing files that are all present on disk.

---

## Self-Check: PASSED

- `README.md` — FOUND
- Commit `76b398e` — FOUND
- `grep "SimTrader Studio (UI)"` — match at line 32
- `grep "docs/README_SIMTRADER.md"` — match at line 100
- `grep "docs/features/FEATURE-simtrader-studio.md"` — match at line 101
- `grep "docs/TODO_SIMTRADER_STUDIO.md"` — match at line 102
- `grep "0 trades"` — match at line 91
- `grep "## Studio UI"` — no match (old stub removed, correct)
- `grep "polyttool"` — no match (no legacy name introduced, correct)

---
*Phase: quick-17*
*Completed: 2026-03-04*
