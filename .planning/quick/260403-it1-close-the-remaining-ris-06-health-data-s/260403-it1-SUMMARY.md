---
phase: quick
plan: 260403-it1
subsystem: research
tags: [ris, monitoring, health-checks, run-log, cli, append_run, deferred-labeling]

# Dependency graph
requires:
  - phase: quick-260403-1sc
    provides: run_log.py, health_checks.py, alert_sink.py, research-health CLI
  - phase: quick-260403-2ow
    provides: APScheduler run_log wiring in scheduler run_job()
provides:
  - research-ingest and research-acquire automatically call append_run() after every run
  - Health checks model_unavailable and rejection_audit_disagreement labeled [DEFERRED] with deferred=True in data dict
  - research-health table footer noting GREEN = no data for deferred checks
  - deferred_checks list in JSON output
  - 14 new tests covering CLI wiring, health truthfulness, and end-to-end integration
affects: [ris-monitoring, research-health, research-ingest, research-acquire]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Non-fatal append_run() pattern: lazy import inside try/except Exception: pass, _t0+_started_at captured before main block"
    - "[DEFERRED] prefix + deferred=True in data dict for stub health checks"
    - "--run-log PATH flag on all RIS CLI commands for override"

key-files:
  created:
    - docs/dev_logs/2026-04-03_ris_r4_manual_producer_health_fix.md
  modified:
    - tools/cli/research_ingest.py
    - tools/cli/research_acquire.py
    - packages/research/monitoring/health_checks.py
    - tools/cli/research_health.py
    - tests/test_ris_monitoring.py
    - docs/features/FEATURE-ris-monitoring-health-v1.md
    - docs/CURRENT_STATE.md

key-decisions:
  - "Non-fatal append_run(): health surface failure must never affect CLI return code — always wrapped in try/except Exception: pass"
  - "Error path run_log: write error record inside except block before return 2, not after (execution skips after return)"
  - "dry-run skip: research-acquire --dry-run exits before run_log write — correct per spec, dry runs leave no trace"
  - "[DEFERRED] labels on model_unavailable and rejection_audit_disagreement make stub status machine-readable via deferred=True in data dict"

patterns-established:
  - "append_run() wiring pattern: import RunRecord+append_run lazily inside try/except, capture _t0+_started_at before execution, write in both success and error paths"

requirements-completed: []

# Metrics
duration: 55min
completed: 2026-04-03
---

# Quick 260403-it1: RIS Manual Producer Health Fix Summary

**Wired research-ingest and research-acquire into append_run() so manual operator runs produce real RunRecords visible to research-health, with [DEFERRED] labeling for stub health checks**

## Performance

- **Duration:** ~55 min
- **Started:** 2026-04-03T16:52:00Z
- **Completed:** 2026-04-03T17:47:12Z
- **Tasks:** 3
- **Files modified:** 7

## Accomplishments

- `research-ingest` and `research-acquire` now automatically call `append_run()` after every run (success, rejection, or error), using the same non-fatal try/except pattern established by the APScheduler wiring
- `model_unavailable` and `rejection_audit_disagreement` health checks now display `[DEFERRED]` in their messages and include `deferred=True, check_type="stub"` in their data dict, preventing false confidence from all-GREEN output
- `research-health` table adds a footer when deferred checks exist: "GREEN = no data, not verified healthy"; JSON output includes a `deferred_checks` list for programmatic inspection
- 14 new tests added (6 CLI wiring, 5 health truthfulness, 3 end-to-end integration) bringing test_ris_monitoring.py to 54 total; full regression: 3582 passed, 0 failed

## Task Commits

Each task was committed atomically:

1. **Task 1: Wire append_run() into research-ingest and research-acquire** - `a098826` (feat)
2. **Task 2: Honest [DEFERRED] labeling + integration tests** - `229ae36` (feat)
3. **Task 3: Update feature doc, dev log, and CURRENT_STATE** - `2142fc3` (docs)

## Files Created/Modified

- `tools/cli/research_ingest.py` - Added `--run-log PATH` arg, timing capture, append_run() in success and error paths
- `tools/cli/research_acquire.py` - Added `--run-log PATH` arg, timing capture, append_run() in URL path success and error paths (skipped on --dry-run)
- `packages/research/monitoring/health_checks.py` - [DEFERRED] prefix and deferred=True data dict for model_unavailable and rejection_audit_disagreement stubs
- `tools/cli/research_health.py` - deferred-checks footer in table output; deferred_checks list in JSON output
- `tests/test_ris_monitoring.py` - 14 new tests in TestCLIRunLogWiring, TestHealthTruthfulness, TestIntegrationIngestToHealth
- `docs/features/FEATURE-ris-monitoring-health-v1.md` - Updated wiring table, deferred items, test count (40→54)
- `docs/CURRENT_STATE.md` - Updated RIS monitoring section with wiring status and new JSON shape
- `docs/dev_logs/2026-04-03_ris_r4_manual_producer_health_fix.md` - Full dev log (created)

## Decisions Made

- Non-fatal append_run() pattern: health surface failure must never affect CLI return code — consistent with APScheduler wiring in run_job()
- Error path write location: run_log write goes inside the `except Exception` block before `return 2`, not after the block (execution would never reach it after return)
- dry-run exemption: `research-acquire --dry-run` exits before timing/run_log setup; correct behavior — dry runs must leave no side effects
- [DEFERRED] machine-readable: `deferred=True` in data dict (not just in message text) so JSON consumers can detect stub checks programmatically

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test fixture too short for ingest minimum**
- **Found during:** Task 1 (test_ingest_writes_run_log and test_run_log_write_failure_is_nonfatal)
- **Issue:** Fixture text "# Test Document\n\nSome prediction market content." was 48 chars; ingestion pipeline requires >= 50 chars minimum, causing acceptance to fail silently (result was rejected, not accepted)
- **Fix:** Extended fixture to "# Test Document\n\nThis document discusses prediction market content, market maker strategies, and arbitrage opportunities." (119 chars)
- **Files modified:** tests/test_ris_monitoring.py
- **Verification:** test_ingest_writes_run_log asserted accepted=1, rejected=0 and passed
- **Committed in:** a098826 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug)
**Impact on plan:** Necessary correctness fix; no scope creep.

## Issues Encountered

- Worktree confusion: agent worktree (`agent-ab894ddb`) is on an old branch lacking all research files. Resolved by working directly against `D:/Coding Projects/Polymarket/PolyTool` (main project on `feat/ws-clob-feed`).

## Known Stubs

Two health checks remain explicitly stubbed and labeled:

| Check | File | Status | Reason |
|-------|------|--------|--------|
| `model_unavailable` | `packages/research/monitoring/health_checks.py` | [DEFERRED] GREEN | Requires provider event data (503 counts) from scheduler |
| `rejection_audit_disagreement` | `packages/research/monitoring/health_checks.py` | [DEFERRED] GREEN | Requires audit runner computing disagreement rate |

Both stubs are intentional and clearly labeled. They do NOT prevent this plan's goal (manual producer wiring + honest health output) from being achieved. Future plans: model_unavailable unblocks when scheduler wires provider error events; rejection_audit_disagreement unblocks when audit tooling plan ships.

## Next Phase Readiness

- All three RIS pipeline entry points (research-ingest, research-acquire, research-scheduler run-job) now write run records automatically
- research-health is a reliable operational visibility tool for the most common operator workflow
- Remaining deferred items (model_unavailable wiring, rejection audit runner) tracked in FEATURE-ris-monitoring-health-v1.md under Deferred Items
- No blockers for RIS Phase 3 (operator feedback loop) or Phase 5 (live source acquisition)

## Self-Check: PASSED

All created/modified files confirmed present on disk. All 3 task commits (a098826, 229ae36, 2142fc3) confirmed in git log.

---
*Phase: quick-260403-it1*
*Completed: 2026-04-03*
