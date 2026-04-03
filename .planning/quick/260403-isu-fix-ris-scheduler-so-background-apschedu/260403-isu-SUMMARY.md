---
phase: quick-260403-isu
plan: 01
subsystem: research-ingestion-system
tags: [scheduler, run-log, apscheduler, bug-fix, tdd]
dependency_graph:
  requires: [packages/research/scheduling/scheduler.py, packages/research/monitoring/run_log.py]
  provides: [fixed start_research_scheduler else branch, _run_log_fn passthrough, TestSchedulerBackgroundPath tests]
  affects: [research-health checks, RIS pipeline run log]
tech_stack:
  added: []
  patterns: [lambda closure with default-arg capture to avoid late-binding]
key_files:
  created:
    - docs/dev_logs/2026-04-03_ris_scheduler_background_fix.md
  modified:
    - packages/research/scheduling/scheduler.py
    - tests/test_ris_scheduler.py
decisions:
  - "Add _run_log_fn to start_research_scheduler() for test injection without filesystem side-effects"
  - "Fix else branch with lambda closure (lambda _jid=jid, _rlf=_run_log_fn: run_job(_jid, _run_log_fn=_rlf)) capturing both vars in default args"
  - "Skip Codex review (scheduling wiring, not execution/risk layer)"
metrics:
  duration_minutes: 4
  completed_date: "2026-04-03"
  tasks_completed: 2
  tasks_total: 2
  files_changed: 3
---

# Phase quick-260403-isu Plan 01: Fix RIS Scheduler Background APScheduler Path Summary

**One-liner:** Fixed APScheduler else branch in start_research_scheduler() to route through run_job() via lambda closure, so every background execution produces a RunRecord in the run log.

---

## What Was Done

### Root Cause

`start_research_scheduler()` had a production bug in its `else` branch (when `_job_runner=None`): it registered the raw job callable directly with APScheduler, bypassing `run_job()` entirely. No `RunRecord` was ever produced for background executions. The `research-health` status checks were vacuously GREEN because the run log was always empty.

### Fix

Two targeted changes to `packages/research/scheduling/scheduler.py`:

1. **Signature change** — added `_run_log_fn: Optional[Callable] = None` to `start_research_scheduler()` so tests can inject a log hook without filesystem side-effects.

2. **Else branch fix** — replaced:
   ```python
   job_fn = _JOB_FN_MAP[callable_name]
   ```
   with:
   ```python
   job_fn = (lambda _jid=jid, _rlf=_run_log_fn: run_job(_jid, _run_log_fn=_rlf))
   ```
   This routes every background APScheduler execution through `run_job()`, which calls `append_run()` after each job completes (success or error).

### Tests Added

Added `TestSchedulerBackgroundPath` (2 tests) to `tests/test_ris_scheduler.py`:
- `test_background_path_writes_run_log` — success path: RunRecord with `exit_status="ok"` produced
- `test_background_path_records_error_status` — error path: RunRecord with `exit_status="error"` produced

Both tests use `_FakeScheduler`, patch `_JOB_FN_MAP` to avoid network calls, and use `records.append` as the injectable log hook.

---

## Test Results

| Suite | Count | Status |
|-------|-------|--------|
| tests/test_ris_scheduler.py | 33 passed (31 pre-existing + 2 new) | PASS |
| tests/test_ris_monitoring.py | 40 passed | PASS |
| Full suite | 3568 passed, 3 deselected, 25 warnings | PASS |

No regressions introduced.

---

## Commits

| Hash | Message |
|------|---------|
| 7c1dd02 | feat(quick-260403-isu-01): fix APScheduler else branch to route through run_job() |
| eeb7a44 | chore(quick-260403-isu-02): add dev log for RIS scheduler background fix |

---

## Deviations from Plan

None — plan executed exactly as written. The two code changes (signature + else branch) and two new tests match the plan specification precisely.

---

## Known Stubs

The `accepted`, `rejected`, `errors` fields in RunRecord remain hardcoded `0` in `run_job()`. These fields require acquisition callables to return structured counts. This is pre-existing behavior unchanged by this fix and is tracked in the RIS_06 backlog.

---

## Self-Check: PASSED

- `packages/research/scheduling/scheduler.py` — exists and contains fixed else branch at line 385
- `tests/test_ris_scheduler.py` — contains `TestSchedulerBackgroundPath` with 2 new tests
- `docs/dev_logs/2026-04-03_ris_scheduler_background_fix.md` — created
- Commits 7c1dd02 and eeb7a44 — present in git log
