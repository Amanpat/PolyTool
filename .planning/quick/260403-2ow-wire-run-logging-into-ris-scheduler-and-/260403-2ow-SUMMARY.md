---
phase: quick-260403-2ow
plan: 01
subsystem: research-ingestion-scheduler
tags: [ris, scheduler, run-log, monitoring, health-checks]
dependency_graph:
  requires: [packages/research/monitoring/run_log.py, packages/research/scheduling/scheduler.py]
  provides: [run_job() with run_log wiring]
  affects: [research-health CLI, evaluate_health()]
tech_stack:
  added: []
  patterns: [injectable hook pattern for offline testability, lazy import inside function]
key_files:
  modified:
    - packages/research/scheduling/scheduler.py
    - tests/test_ris_scheduler.py
  created:
    - docs/dev_logs/2026-04-03_ris_r4_runlog_wiring.md
decisions:
  - Lazy import of RunRecord/append_run inside run_job() avoids coupling at module-load time
  - _run_log_fn injectable hook enables offline testing without filesystem writes
  - run_log write failures are swallowed with WARNING -- never affect run_job return code
  - accepted/rejected/errors all set to 0 (jobs don't return counts yet -- tracked as known stub)
metrics:
  duration: "~10 minutes"
  completed: "2026-04-03"
  tasks_completed: 2
  files_modified: 2
  files_created: 1
---

# Phase quick-260403-2ow Plan 01: Wire run_log into run_job Summary

## One-liner

Wired `append_run()` into `run_job()` via injectable `_run_log_fn` hook with non-fatal error swallowing, producing `RunRecord` entries (exit_status=ok/error) for every known job execution.

## What Was Built

### `packages/research/scheduling/scheduler.py`

`run_job()` now accepts an optional `_run_log_fn=None` parameter. When `None`,
the real `append_run` from `run_log.py` is lazy-imported and called. When
provided, the callable is used instead (test hook).

Key behaviors:
- `started_at` captured before fn() call (ISO-8601 UTC, microseconds=0)
- Wall-clock timing via `time.monotonic()` around fn() call
- `RunRecord` built in `finally` block with `exit_status="ok"` on success or
  `"error"` on exception
- `log_fn(record)` wrapped in `try/except` -- write failures log WARNING and are
  swallowed; run_job return code is determined solely by fn() success/failure
- Unknown job_id early-return paths remain unchanged (no record written)

### `tests/test_ris_scheduler.py`

Added `TestRunJobRunLog` with 3 new tests:

| Test | Status | Verifies |
|---|---|---|
| `test_run_job_writes_run_log_on_success` | PASS | exit_status=ok, pipeline=job_id, duration>=0 |
| `test_run_job_writes_run_log_on_error` | PASS | exit_status=error, result=1 |
| `test_run_job_to_health_end_to_end` | PASS | Full pipeline: run_job -> append_run -> list_runs -> evaluate_health GREEN |

## Deviations from Plan

None — plan executed exactly as written.

## Test Results

```
tests/test_ris_scheduler.py:  31 passed (28 existing + 3 new)
tests/test_ris_monitoring.py: 40 passed
Full suite: 3566 passed, 0 failed, 3 deselected, 25 warnings
```

## Commits

| Hash | Message |
|---|---|
| `498c77c` | feat(quick-260403-2ow-01): wire append_run into run_job with injectable hook |

## Known Stubs

- `accepted=0, rejected=0, errors=0` hardcoded in all RunRecords produced by `run_job()`.
  - File: `packages/research/scheduling/scheduler.py` (in the `finally` block of `run_job`)
  - Reason: Job callables currently return `None` and don't expose doc counts.
    This is intentional and tracked in the RIS_06 backlog. The `no_new_docs_48h`
    health check will report YELLOW as long as accepted=0, which is the correct
    observable signal that acquisition jobs don't expose counts yet.
  - Resolution: A future plan will wire doc-count return values from acquisition
    job callables into the RunRecord fields.

## Self-Check: PASSED
