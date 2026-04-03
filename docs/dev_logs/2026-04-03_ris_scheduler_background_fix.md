# Dev Log: RIS Scheduler Background Fix

**Date:** 2026-04-03
**Packet:** quick-260403-isu
**Branch:** feat/ws-clob-feed

---

## Objective

Fix `start_research_scheduler()` so real APScheduler background executions go through
`run_job()` — the same logged execution path used by the `research-scheduler run-job` CLI.

---

## Root Cause

In `packages/research/scheduling/scheduler.py`, the `start_research_scheduler()` function
registers APScheduler jobs in a loop. When `_job_runner=None` (the production default),
the `else` branch registered the raw `_JOB_FN_MAP[callable_name]` function directly:

```python
# BUG: bypasses run_job(), no RunRecord produced
else:
    job_fn = _JOB_FN_MAP[callable_name]
```

This bypassed `run_job()` entirely, so `append_run()` was never called for background
executions. The run log stayed empty; `research-health` showed vacuous GREEN checks based
on zero data rather than real execution outcomes.

---

## Fix

Two changes to `packages/research/scheduling/scheduler.py`:

**Change 1 — Add `_run_log_fn` to `start_research_scheduler()` signature:**

```python
def start_research_scheduler(
    _scheduler_factory: Optional[Callable[[], Any]] = None,
    _job_runner: Optional[Callable[[str], None]] = None,
    _run_log_fn: Optional[Callable] = None,   # <-- new
) -> Any:
```

This allows tests to inject a log hook without filesystem side-effects. In production
(`_run_log_fn=None`), `run_job()` uses the real `append_run` from the run_log module.

**Change 2 — Fix the `else` branch:**

```python
# Before
else:
    job_fn = _JOB_FN_MAP[callable_name]

# After
else:
    # Always route through run_job() so every background execution is logged.
    # Capture jid and _run_log_fn in default args to avoid late-binding closure.
    job_fn = (lambda _jid=jid, _rlf=_run_log_fn: run_job(_jid, _run_log_fn=_rlf))
```

The `_job_runner` branch is unchanged — it is a test-injection path only and has no
need for log passthrough.

---

## Tests

Added `TestSchedulerBackgroundPath` class to `tests/test_ris_scheduler.py`:

- `test_background_path_writes_run_log`: verifies that invoking a registered APScheduler
  job fn (no `_job_runner`) produces a RunRecord with `pipeline="academic_ingest"` and
  `exit_status="ok"`.
- `test_background_path_records_error_status`: verifies that when the underlying callable
  raises, the RunRecord has `exit_status="error"`.

Both tests use `_FakeScheduler` (already in test file), patch `_JOB_FN_MAP` directly to
avoid network calls, and use `records.append` as the `_run_log_fn` hook.

**Scheduler test results:** 33 passed (31 pre-existing + 2 new).

**Full suite results:** 3568 passed, 3 deselected, 25 warnings — no regressions.

---

## Codex Review

Tier: Skip — scheduling wiring change, not in execution/risk/kill-switch layer.
No adversarial review required per CLAUDE.md Codex Review Policy.

---

## Open Questions / Future Work

- `accepted`, `rejected`, `errors` fields in RunRecord remain hardcoded `0`. These
  require acquisition callables to return structured counts rather than `None`. This is
  tracked in the RIS_06 backlog as a future task (not blocking correctness of run logging
  itself — the pipeline id, timestamp, duration, and exit_status are all correct now).
