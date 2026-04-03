---
phase: quick-260403-isu
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - packages/research/scheduling/scheduler.py
  - tests/test_ris_scheduler.py
  - docs/dev_logs/2026-04-03_ris_scheduler_background_fix.md
autonomous: true
requirements:
  - RIS_06_scheduler_run_log
must_haves:
  truths:
    - "APScheduler background jobs call run_job() so every execution is logged"
    - "Manually triggered jobs (run-job CLI) still call run_job() and are logged"
    - "All 31 existing scheduler tests pass unchanged"
    - "Two new tests prove the real APScheduler path registers run_job() wrappers"
  artifacts:
    - path: "packages/research/scheduling/scheduler.py"
      provides: "Fixed start_research_scheduler — else branch registers run_job wrapper"
      contains: "lambda _jid=jid: run_job(_jid)"
    - path: "tests/test_ris_scheduler.py"
      provides: "Two new tests in TestSchedulerBackgroundPath covering the real APScheduler path"
  key_links:
    - from: "start_research_scheduler() else branch"
      to: "run_job()"
      via: "lambda wrapper registered with APScheduler"
      pattern: "lambda _jid=jid: run_job\\(_jid\\)"
---

<objective>
Fix `start_research_scheduler()` so real APScheduler background executions go through
`run_job()` — the same logged path used by the `research-scheduler run-job` CLI.

Currently, when `_job_runner=None` (production default), the `else` branch at line 377
registers the raw `_JOB_FN_MAP[callable_name]` function directly with APScheduler.
This bypasses `run_job()` entirely, so `append_run()` is never called for background
executions and the RunRecord run log stays empty.

Purpose: All scheduled executions must produce RunRecord entries so `research-health`
shows real pipeline status rather than vacuous GREEN checks.

Output:
- `scheduler.py` — one-line fix in `else` branch; also accept optional `_run_log_fn`
  passthrough from `start_research_scheduler()` to `run_job()` so tests can inject
  a log hook without touching the filesystem.
- `tests/test_ris_scheduler.py` — two new tests in `TestSchedulerBackgroundPath`.
- Dev log.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Coding Projects/Polymarket/PolyTool/packages/research/scheduling/scheduler.py
@D:/Coding Projects/Polymarket/PolyTool/tests/test_ris_scheduler.py
@D:/Coding Projects/Polymarket/PolyTool/packages/research/monitoring/run_log.py

<interfaces>
<!-- Key signatures the executor needs. Do NOT explore further. -->

From packages/research/scheduling/scheduler.py (current broken code):

```python
def start_research_scheduler(
    _scheduler_factory: Optional[Callable[[], Any]] = None,
    _job_runner: Optional[Callable[[str], None]] = None,
) -> Any:
    ...
    for job_entry in JOB_REGISTRY:
        jid = job_entry["id"]
        callable_name = job_entry["callable_name"]

        if _job_runner is not None:
            job_fn = (lambda _jid=jid: _job_runner(_jid))   # ← tested path: passes job_id
        else:
            job_fn = _JOB_FN_MAP[callable_name]              # ← BUG: bypasses run_job()

        scheduler.add_job(job_fn, trigger, id=jid, name=jname)
```

Bug location: line 377 (`else` branch). Fix: replace with a lambda that calls `run_job(jid)`.

The `run_job()` signature:
```python
def run_job(job_id: str, _run_log_fn: Optional[Callable] = None) -> int:
```

The injectable `_run_log_fn` is already passed through `run_job()` when the CLI calls
`run_job` directly. To make tests for the background path possible without filesystem
side-effects, add an optional `_run_log_fn` parameter to `start_research_scheduler()` and
thread it through the lambda in the `else` branch.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Fix else branch in start_research_scheduler() and add run_log_fn passthrough</name>
  <files>packages/research/scheduling/scheduler.py, tests/test_ris_scheduler.py</files>
  <behavior>
    - Test A: When start_research_scheduler() is called with a real _scheduler_factory but
      NO _job_runner, the registered APScheduler job fn calls run_job(), not the raw callable.
      Verify by: providing a _run_log_fn that appends records, invoke the registered job fn
      manually, assert a RunRecord was produced with pipeline == job_id.
    - Test B: When the registered job fn is invoked and the underlying callable raises,
      the RunRecord has exit_status="error" (run_job's existing error handling fires).
    - All 31 pre-existing tests pass unchanged.
  </behavior>
  <action>
    CHANGE 1 — Fix the `else` branch (the only code change required in the logic):

    In `start_research_scheduler()`, replace:
    ```python
    else:
        job_fn = _JOB_FN_MAP[callable_name]
    ```
    with:
    ```python
    else:
        # Always route through run_job() so every background execution is logged.
        # Capture jid and _run_log_fn in default args to avoid late-binding closure.
        job_fn = (lambda _jid=jid, _rlf=_run_log_fn: run_job(_jid, _run_log_fn=_rlf))
    ```

    CHANGE 2 — Add `_run_log_fn` parameter to `start_research_scheduler()` signature
    so tests can inject a log hook without touching the filesystem:

    ```python
    def start_research_scheduler(
        _scheduler_factory: Optional[Callable[[], Any]] = None,
        _job_runner: Optional[Callable[[str], None]] = None,
        _run_log_fn: Optional[Callable] = None,
    ) -> Any:
    ```

    No other changes to `start_research_scheduler()` are needed.

    CHANGE 3 — Add `TestSchedulerBackgroundPath` class to `tests/test_ris_scheduler.py`:

    ```python
    class TestSchedulerBackgroundPath:
        """Verify that real APScheduler path (no _job_runner) routes through run_job()."""

        def test_background_path_writes_run_log(self) -> None:
            """Registered job fn calls run_job(), which produces a RunRecord."""
            from packages.research.scheduling import scheduler as sched_mod
            from packages.research.monitoring.run_log import RunRecord

            records: list = []
            fake = _FakeScheduler()

            # Patch the actual callable so no network calls happen
            mock_fn = MagicMock(return_value=None)
            original = sched_mod._JOB_FN_MAP["_job_run_academic_ingestion"]
            sched_mod._JOB_FN_MAP["_job_run_academic_ingestion"] = mock_fn
            try:
                sched_mod.start_research_scheduler(
                    _scheduler_factory=lambda: fake,
                    # No _job_runner — exercises the else branch (real path)
                    _run_log_fn=records.append,
                )
                # Find the academic_ingest job and invoke it manually
                job = next(j for j in fake.jobs if j["id"] == "academic_ingest")
                job["fn"]()
            finally:
                sched_mod._JOB_FN_MAP["_job_run_academic_ingestion"] = original

            assert len(records) == 1
            rec = records[0]
            assert isinstance(rec, RunRecord)
            assert rec.pipeline == "academic_ingest"
            assert rec.exit_status == "ok"

        def test_background_path_records_error_status(self) -> None:
            """When callable raises, the RunRecord has exit_status='error'."""
            from packages.research.scheduling import scheduler as sched_mod
            from packages.research.monitoring.run_log import RunRecord

            records: list = []
            fake = _FakeScheduler()

            mock_fn = MagicMock(side_effect=RuntimeError("boom"))
            original = sched_mod._JOB_FN_MAP["_job_run_academic_ingestion"]
            sched_mod._JOB_FN_MAP["_job_run_academic_ingestion"] = mock_fn
            try:
                sched_mod.start_research_scheduler(
                    _scheduler_factory=lambda: fake,
                    _run_log_fn=records.append,
                )
                job = next(j for j in fake.jobs if j["id"] == "academic_ingest")
                job["fn"]()
            finally:
                sched_mod._JOB_FN_MAP["_job_run_academic_ingestion"] = original

            assert len(records) == 1
            assert records[0].exit_status == "error"
    ```

    Note: The `_FakeScheduler` class already exists in the test file and can be reused.
    The `MagicMock` and `patch` imports already exist at the top of the test file.

    Do NOT add `_run_log_fn` to the `_job_runner` branch — that branch is for test
    injection only and has no need for log passthrough.
  </action>
  <verify>
    <automated>cd "D:/Coding Projects/Polymarket/PolyTool" && rtk python -m pytest tests/test_ris_scheduler.py -v --tb=short 2>&1 | tail -20</automated>
  </verify>
  <done>
    All 33 tests in test_ris_scheduler.py pass (31 existing + 2 new).
    The else branch in start_research_scheduler() now reads:
    `job_fn = (lambda _jid=jid, _rlf=_run_log_fn: run_job(_jid, _run_log_fn=_rlf))`
  </done>
</task>

<task type="auto">
  <name>Task 2: Full regression check and dev log</name>
  <files>docs/dev_logs/2026-04-03_ris_scheduler_background_fix.md</files>
  <action>
    Run the full test suite to confirm no regressions:
    ```bash
    cd "D:/Coding Projects/Polymarket/PolyTool" && rtk python -m pytest tests/ -x -q --tb=short 2>&1 | tail -10
    ```

    Then write `docs/dev_logs/2026-04-03_ris_scheduler_background_fix.md`:

    - Objective: Fix APScheduler background path to route through run_job()
    - Root cause: else branch in start_research_scheduler() registered raw callable
      instead of a run_job() wrapper
    - Fix: one-line change to else branch + _run_log_fn parameter added to signature
    - Tests: 2 new tests in TestSchedulerBackgroundPath; 33 total in test_ris_scheduler.py
    - Full suite count: report exact passing count from test run output
    - Codex review: Skip tier (scheduling wiring, not execution/risk layer)
    - Open questions: accepted/rejected/errors still hardcoded 0 — doc counts require
      acquisition callables to expose a return value (future work, tracked in RIS_06 backlog)
  </action>
  <verify>
    <automated>cd "D:/Coding Projects/Polymarket/PolyTool" && python -m pytest tests/test_ris_scheduler.py tests/test_ris_monitoring.py -q --tb=short 2>&1 | tail -5</automated>
  </verify>
  <done>
    Full test suite passes with no regressions.
    Dev log written to docs/dev_logs/2026-04-03_ris_scheduler_background_fix.md.
    Exact test count reported.
  </done>
</task>

</tasks>

<verification>
After both tasks:
1. `tests/test_ris_scheduler.py` — 33 tests pass (31 pre-existing + 2 new)
2. `packages/research/scheduling/scheduler.py` line in else branch reads:
   `job_fn = (lambda _jid=jid, _rlf=_run_log_fn: run_job(_jid, _run_log_fn=_rlf))`
3. `start_research_scheduler()` signature has `_run_log_fn: Optional[Callable] = None`
4. No other changes to scheduler.py (job callables, JOB_REGISTRY, _JOB_FN_MAP untouched)
5. Full test suite shows no regressions
</verification>

<success_criteria>
- Background APScheduler jobs route through run_job() — same logged execution path as manual CLI invocation
- RunRecord with correct pipeline id and exit_status is produced for every background execution
- No regressions in the 31 pre-existing scheduler tests
- Two new tests cover the previously untested background path (no _job_runner branch)
- accepted/rejected/errors fields remain 0 (unchanged — doc counts are a future task)
</success_criteria>

<output>
After completion, create `.planning/quick/260403-isu-fix-ris-scheduler-so-background-apschedu/260403-isu-SUMMARY.md`
using the summary template.
</output>
