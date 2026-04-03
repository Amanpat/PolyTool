# Dev Log: RIS_06 APScheduler Scheduler Module v1

**Date:** 2026-04-03
**Task:** quick-260403-1s3 — Complete the APScheduler runtime side of RIS_06 Infrastructure
**Branch:** feat/ws-clob-feed

---

## Summary

Built the APScheduler background scheduling layer for RIS v1. The scheduler registers 8 named
periodic jobs that delegate to existing RIS CLI main() functions. No new network logic was
added — all job callables are thin wrappers. Twitter/X is explicitly excluded per the
deferred-fetcher decision from RIS_02.

---

## Files Created / Modified

| File | Action |
|------|--------|
| `packages/research/scheduling/__init__.py` | Created — package marker with re-exports |
| `packages/research/scheduling/scheduler.py` | Created — core scheduler module |
| `tools/cli/research_scheduler.py` | Created — CLI: status / start / run-job |
| `polytool/__main__.py` | Modified — registered research-scheduler command |
| `pyproject.toml` | Modified — [ris] optional dep group, packages.research.scheduling |
| `tests/test_ris_scheduler.py` | Created — 28 offline unit tests |
| `docs/features/FEATURE-ris-scheduler-v1.md` | Created — feature documentation |
| `docs/CURRENT_STATE.md` | Modified — RIS scheduler bullet added |

---

## Design Decisions

### Lazy APScheduler Import

APScheduler is imported inside `start_research_scheduler()` only (not at module level).
This means `JOB_REGISTRY`, all job callables, and `run_job()` are importable even when
APScheduler is not installed. The `[ris]` optional dep group is opt-in and not added to
`[all]`.

### `_JOB_FN_MAP` Patching Pattern for Tests

Job callables use `import tools.cli.research_acquire as research_acquire` (lazy import
inside the function body). In the full test suite, `tools.cli.research_acquire` is already
imported as a real module by prior tests. Python's import machinery, when the parent module
is already loaded, may bypass `sys.modules` patch for the child and return the attribute from
the cached parent module. To avoid this ordering-dependent test fragility, tests that need to
intercept job callables patch `sched_mod._JOB_FN_MAP["_job_run_..."]` directly. This is
reliable regardless of import order and does not depend on `sys.modules` state.

### `_job_runner` Injectable Hook

`start_research_scheduler()` accepts an optional `_job_runner: Callable[[str], None]` that
replaces all job callables with `lambda: _job_runner(job_id)`. This enables fully offline
scheduler tests: pass a `_FakeScheduler` and a collector list. The closure uses a default
argument to avoid late-binding issues with `jid`.

### Twitter/X Excluded

Twitter/X social ingestion is explicitly not registered. The `LiveTwitterFetcher` does not
exist yet (deferred per RIS_02 spec). The status command and dry-run output both include a
note: "Note: Twitter/X ingestion is not scheduled (fetcher not yet implemented)."

### `run_job()` Return Contract

`run_job(job_id) -> int` returns 0 on success, 1 on unknown id or exception. Exceptions are
logged (not propagated) so a single job failure does not crash the scheduler or CLI process.

---

## Test Results

- **New tests:** 28 in `tests/test_ris_scheduler.py`
- **Target:** 15+ (exceeded)
- **Network calls in tests:** None (all external calls intercepted via `_JOB_FN_MAP` patching
  or `_FakeScheduler` + `_job_runner` injection)
- **Full regression:** 3557 passed, 0 failed, 3 deselected, 25 warnings

Test classes:
- `TestJobRegistry` (6 tests) — registry length, no twitter_ingest, required keys, unique ids,
  expected ids, importable without APScheduler
- `TestStartResearchScheduler` (6 tests) — returns instance, started, 8 jobs registered,
  ids match, runner receives correct job_id, no jobs triggered at start
- `TestRunJob` (4 tests) — unknown id returns 1, academic returns 0, weekly_digest returns 0,
  exception returns 1
- `TestCliStatus` (4 tests) — returns 0, JSON returns 0 with valid list, required keys, 8 ids
- `TestCliStart` (2 tests) — dry-run returns 0, dry-run lists jobs
- `TestCliRunJob` (4 tests) — unknown id returns 1, known id returns 0, JSON flag, error JSON
- `TestCliMissingSubcommand` (2 tests) — missing returns 1, unknown returns 1 (or SystemExit != 0)

---

## Codex Review

Skipped — no execution, risk, kill-switch, or order placement code touched. This task
created a scheduling wrapper over existing CLI functions only.

---

## Open Issues / Follow-up

- `freshness_refresh` is a lightweight placeholder (calls academic ingest with "prediction
  markets 2026"). Full freshness recalculation logic is deferred to a later RIS task.
- Twitter/X ingestion: blocked on `LiveTwitterFetcher` implementation (RIS_02 spec).
- APScheduler v4 compatibility: the `[ris]` dep group pins `<4.0` deliberately. APScheduler
  v4 has a different API (async-first). Update when the project migrates.
- Production deployment: the `start` subcommand runs a blocking loop. For production use,
  wrap in a systemd service, Docker container, or supervisor process.
