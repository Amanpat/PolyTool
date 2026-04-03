# 2026-04-03 — RIS R4: Wire run_log into run_job (quick-260403-2ow)

## Objective

Wire `append_run()` from `packages/research/monitoring/run_log.py` into the
`run_job()` execution path in `packages/research/scheduling/scheduler.py` so
every scheduled or manually-triggered research job produces a `RunRecord` in
the JSONL run log.

Without this wiring the health check system (`research-health` CLI,
`evaluate_health()`) receives no run data and all checks are vacuously GREEN.

## What was done

### `packages/research/scheduling/scheduler.py`

- Added `import time` and `from datetime import datetime, timezone` at the top.
- Extended `run_job(job_id, _run_log_fn=None)` with an optional injectable hook:
  - `_run_log_fn=None` defaults to the real `append_run` via lazy import (no
    coupling at module-load time).
  - Providing a replacement callable enables offline testing without touching the
    filesystem.
- Captures `started_at` (ISO-8601 UTC) and wall-clock timing with
  `time.monotonic()` around the `fn()` call.
- Builds a `RunRecord` in the `finally` block (runs whether `fn()` succeeds or
  raises):
  - `pipeline = job_id`
  - `exit_status = "ok"` on success, `"error"` on exception
  - `accepted = rejected = errors = 0` (jobs don't return doc counts yet)
- Calls `log_fn(record)` inside a `try/except` — run-log write failures log a
  WARNING and are swallowed; `run_job` return code is never affected by run-log
  failures.
- Unknown job_id early-return paths are unchanged — no record is written.

### `tests/test_ris_scheduler.py`

Added `TestRunJobRunLog` with 3 new tests:

| Test | What it verifies |
|---|---|
| `test_run_job_writes_run_log_on_success` | Successful job writes RunRecord, exit_status=ok |
| `test_run_job_writes_run_log_on_error` | Raising job writes RunRecord, exit_status=error |
| `test_run_job_to_health_end_to_end` | run_job -> append_run -> list_runs -> evaluate_health GREEN |

All tests use the injectable `_run_log_fn` hook and `tmp_path` — no network
calls, no filesystem side-effects in CI.

## Test results

```
tests/test_ris_scheduler.py  31 passed  (28 existing + 3 new)
tests/test_ris_monitoring.py 40 passed
Full suite: 3566 passed, 0 failed, 3 deselected, 25 warnings
```

## Codex review

Tier: Skip (monitoring/scheduling wiring, not execution/risk layer). No review required per policy.

## Commit

`498c77c` feat(quick-260403-2ow-01): wire append_run into run_job with injectable hook

## Open questions / future work

- Jobs currently emit `accepted=0, rejected=0` — health check `no_new_docs_48h`
  will always be YELLOW once run data exists. This is expected and will be
  resolved when acquisition jobs expose doc counts (tracked in RIS_06 backlog).
- The `research-health` CLI will now show real pipeline_failed data after any
  job executes.
