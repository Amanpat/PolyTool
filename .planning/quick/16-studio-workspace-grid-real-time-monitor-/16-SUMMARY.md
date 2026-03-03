---
phase: 16-studio-workspace-grid-real-time-monitor-
plan: 01
subsystem: ui
tags: [simtrader, studio, fastapi, vanilla-js, websocket, workspace, monitor]

# Dependency graph
requires:
  - phase: 12-implement-simtrader-studio-mvp-local-fas
    provides: Studio FastAPI app, session manager, index.html workspace panel
  - phase: 13-add-simtrader-studio-ondemand-tab-manual
    provides: OnDemand session state, portfolio_snapshot fields
provides:
  - GET /api/sessions/{id}/monitor — lightweight session stats endpoint
  - wsMonitorCache/wsMonitorFetching — 1s-refresh monitor cache in JS state
  - Enhanced renderWorkspaceSessionCard with live metrics + Kill/Open Report buttons
  - Enhanced renderWorkspaceOnDemandCard with cursor, cash, equity, net PnL
  - Enhanced renderWorkspaceArtifactCard with strategy, PnL, top rejection, Open Viewer
  - openSimulationArtifact(key) helper for workspace-to-simulation tab navigation
affects: [studio, workspace, simtrader-studio]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Monitor cache pattern: in-flight Set prevents duplicate concurrent fetches; stale data preserved on transient failure
    - Dual interval pattern: 3s for full state refresh, 1s for monitor-only re-render
    - Lightweight stats endpoint: reads only manifest + summary JSON, no JSONL row loading

key-files:
  created: []
  modified:
    - packages/polymarket/simtrader/studio/app.py
    - packages/polymarket/simtrader/studio/static/index.html
    - tests/test_simtrader_studio.py

key-decisions:
  - "Monitor endpoint reads only run_manifest.json and summary.json — no equity_curve/orders/fills JSONL loading"
  - "wsMonitorFetching Set prevents redundant concurrent fetches; stale wsMonitorCache preserved on failure"
  - "1s interval refreshes monitor cache + re-renders workspace panel; 3s poll does full state + logs + monitor"
  - "openSimulationArtifact() sets state.simulation.selectedArtifactKey then activates simulation tab"
  - "Kill button shown only for active statuses (running/starting/terminating); Open Report shown only when report_url present"

patterns-established:
  - "Monitor cache pattern: wsMonitorFetching guards against duplicate in-flight fetches"
  - "Dual interval: lightweight 1s render from cache + heavyweight 3s full refresh"

# Metrics
duration: 20min
completed: 2026-03-03
---

# Quick-16: Studio Workspace Grid Real-Time Monitor Summary

**Workspace source cards upgraded with live monitor metrics: session cards show events/reconnects/stalls/PnL/kill button; artifact cards show strategy/PnL/top-rejection/viewer link; OnDemand cards show cursor/cash/equity — all updating at 1s cadence from a lightweight `/api/sessions/{id}/monitor` backend endpoint.**

## Performance

- **Duration:** ~20 min
- **Completed:** 2026-03-03
- **Tasks:** 2/2
- **Files modified:** 3

## Accomplishments

- Added `GET /api/sessions/{id}/monitor` — reads only `run_manifest.json` + `summary.json`, returns `run_metrics` (events_received, ws_reconnects, ws_timeouts), net_profit, strategy, decisions/orders/fills counts. No heavy JSONL loading.
- Added `wsMonitorCache` (Map) and `wsMonitorFetching` (Set) to frontend state; `refreshWorkspaceMonitorMetrics()` fetches all workspace session IDs in parallel with in-flight guard.
- Boot: 3s poll now runs `refreshWorkspaceSessionLogs` + `refreshWorkspaceMonitorMetrics` in parallel; separate 1s `setInterval` refreshes monitor cache and re-renders workspace panel.
- `renderWorkspaceSessionCard`: 12-field kv display (status, kind, started, events, reconnects, stalls, decisions, orders, fills, net PnL, last log); Kill button for active sessions; Open Report button when report_url present.
- `renderWorkspaceOnDemandCard`: cursor/total/pct, timestamp, open orders, cash, equity, net PnL from `portfolio_snapshot`.
- `renderWorkspaceArtifactCard`: strategy, net PnL, dominant rejection reason + count, orders/fills counts; Open Viewer button calls `openSimulationArtifact(key)` which activates simulation tab with artifact pre-selected.
- 3 new test cases (19 total): no-artifact-dir, with-artifact-dir (reads manifest+summary), unknown-returns-404.

## Task Commits

1. **Task 1: Add GET /api/sessions/{id}/monitor backend endpoint** - `ec0de0a` (feat)
2. **Task 2: Frontend monitor cache + enhanced session/artifact/ondemand cards** - `c3f5e73` (feat)

## Files Created/Modified

- `packages/polymarket/simtrader/studio/app.py` — Added `session_monitor` endpoint after `/log` route; reads run_manifest + summary, returns lightweight stats shape
- `packages/polymarket/simtrader/studio/static/index.html` — State additions, refreshWorkspaceMonitorMetrics(), 1s interval in boot(), three enhanced card render functions, openSimulationArtifact() helper
- `tests/test_simtrader_studio.py` — 3 new tests for the monitor endpoint

## Decisions Made

- Monitor endpoint reads only `run_manifest.json` and `summary.json` (not equity_curve/orders/fills/decisions JSONL arrays) to stay lightweight for 1s polling.
- `wsMonitorFetching` Set prevents duplicate concurrent fetches; stale cache is preserved on transient network failure (don't evict).
- Dual interval: 1s lightweight interval refreshes monitor cache + re-renders; 3s heavy interval does full state + logs + monitor together.
- `openSimulationArtifact(key)` sets `state.simulation.selectedArtifactKey`, clears payload/filtered, activates simulation tab, then calls `loadSimulationSelected()` — reuses existing simulation tab machinery without new routes.
- Kill button shows only for `["running", "starting", "terminating"]` statuses; Open Report button requires `report_url` truthy (set by `_decorate_session_snapshot` when `report.html` exists).

## Deviations from Plan

**1. [Rule 1 - Bug] Test for monitor-with-artifact-dir used shadow command which doesn't auto-assign --run-id**
- **Found during:** Task 1 (writing monitor endpoint test)
- **Issue:** Shadow sessions don't receive `--run-id` arg; the test's `command_builder` assertion on `run_id` always failed for `shadow` kind
- **Fix:** Changed test to use `run` command (which does get `--run-id` passed by `StudioSessionManager`) and `runs/` subdir
- **Files modified:** `tests/test_simtrader_studio.py`
- **Verification:** All 19 tests pass
- **Committed in:** ec0de0a (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 bug — test setup)
**Impact on plan:** Minimal; test logic fixed, no scope change.

## Issues Encountered

None beyond the test fix above.

## Self-Check: PASSED

Files verified:
- `packages/polymarket/simtrader/studio/app.py` — contains `session_monitor` endpoint
- `packages/polymarket/simtrader/studio/static/index.html` — contains `wsMonitorCache`, `refreshWorkspaceMonitorMetrics`, updated card functions, `openSimulationArtifact`
- `tests/test_simtrader_studio.py` — contains 3 new monitor tests

Commits verified:
- `ec0de0a` — backend endpoint + 3 tests
- `c3f5e73` — frontend monitor cache + enhanced cards

## Next Phase Readiness

- Workspace grid is now a live monitoring dashboard for concurrent shadow/run/ondemand sessions
- Kill and Open Viewer actions are wired and functional
- Studio ready for batch/sweep workflow integration or further UI refinement

---
*Phase: 16-studio-workspace-grid-real-time-monitor-*
*Completed: 2026-03-03*
