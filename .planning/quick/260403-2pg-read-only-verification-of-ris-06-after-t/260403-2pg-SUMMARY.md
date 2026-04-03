---
phase: quick-260403-2pg
plan: 01
subsystem: research-infrastructure
tags: [ris, verification, monitoring, scheduler, ops-cli]
dependency_graph:
  requires: []
  provides: [RIS_06_verification_report]
  affects: [260403-2ow, 260403-2p9]
tech_stack:
  added: []
  patterns: []
key_files:
  created:
    - .planning/quick/260403-2pg-read-only-verification-of-ris-06-after-t/260403-2pg-SUMMARY.md
  modified: []
decisions:
  - "RIS_06 verdict: VERIFIED — all three originally-planned gaps are already resolved in the codebase. Plans 2ow and 2p9 appear to have landed ahead of this verification run."
metrics:
  duration: "~10 minutes"
  completed: "2026-04-03"
  tasks_completed: 2
  files_changed: 1
---

# Phase quick-260403-2pg Plan 01: RIS_06 Read-Only Verification Summary

One-liner: RIS_06 scheduler + monitoring + ops-CLI fully wired — all 3 test suites pass (31 + 40 + 21 = 92 total), append_run IS wired in run_job(), CLI tests exist for research-stats, and all 3 commands are registered in __main__.py.

---

## VERDICT

RIS_06 v1: **VERIFIED**

All three gaps anticipated by the plan template (Gap 1: run_log wiring, Gap 2: stale CLI names in spec, Gap 3: missing stats CLI tests) have already been resolved. The code, tests, and partial doc fixes landed before this verification ran. One residual doc gap remains (research-health CLI not listed in spec's CLI reference section) but does not affect runtime correctness.

---

## EVIDENCE

### Files Found

| File | Status | Key Symbols Present |
|------|--------|---------------------|
| packages/research/monitoring/run_log.py | FOUND | RunRecord (all fields: pipeline, started_at, duration_s, accepted, rejected, errors, exit_status), append_run, list_runs, load_last_run (inferred), DEFAULT_RUN_LOG_PATH |
| packages/research/monitoring/health_checks.py | FOUND | HealthCheck, HealthCheckResult, ALL_CHECKS (6 checks), evaluate_health |
| packages/research/monitoring/alert_sink.py | FOUND | AlertSink (Protocol), LogSink, WebhookSink, fire_alerts |
| packages/research/metrics.py | FOUND | RisMetricsSnapshot, collect_ris_metrics, format_metrics_summary |
| packages/research/scheduling/scheduler.py | FOUND | JOB_REGISTRY (8 jobs), start_research_scheduler, run_job |
| tools/cli/research_scheduler.py | FOUND | main() entrypoint |
| tools/cli/research_health.py | FOUND | main() entrypoint |
| tools/cli/research_stats.py | FOUND | main() entrypoint |
| docs/features/FEATURE-ris-monitoring-health-v1.md | FOUND | - |
| docs/features/FEATURE-ris-ops-cli-and-metrics.md | FOUND | - |
| docs/features/FEATURE-ris-scheduler-v1.md | FOUND | - |

### Key Symbols Found

**run_log.py — RunRecord dataclass fields confirmed:**
- pipeline, started_at, duration_s, accepted, rejected, errors, exit_status (Literal["ok", "error", "partial"])
- DEFAULT_RUN_LOG_PATH = Path("artifacts/research/run_log.jsonl")
- Functions: append_run, list_runs (confirmed by import in scheduler), _make_run_id

**health_checks.py — ALL_CHECKS confirmed (6 entries):**
1. pipeline_failed
2. no_new_docs_48h
3. accept_rate_low
4. accept_rate_high
5. model_unavailable (GREEN stub — documented, awaiting ProviderEvent data)
6. rejection_audit_disagreement

**scheduler.py — run_job() append_run wiring confirmed:**

```
packages/research/scheduling/scheduler.py:254 — def run_job(job_id: str, _run_log_fn: Optional[Callable] = None) -> int:
packages/research/scheduling/scheduler.py:293 — # Lazy import of RunRecord and append_run to avoid coupling at module load.
packages/research/scheduling/scheduler.py:295 — from packages.research.monitoring.run_log import RunRecord, append_run  # noqa: PLC0415
packages/research/scheduling/scheduler.py:306 — log_fn = _run_log_fn if _run_log_fn is not None else append_run
```

The `_run_log_fn` injectable parameter and lazy import pattern are fully implemented. Every run_job() invocation writes a RunRecord in its `finally` block (non-fatal if writing fails).

**JOB_REGISTRY — 8 entries confirmed via CLI:**
academic_ingest, reddit_polymarket, reddit_others, blog_ingest, youtube_ingest, github_ingest, freshness_refresh, weekly_digest.

### CLI Wiring Found

All three CLIs registered in polytool/__main__.py at all three required locations:

- **Entrypoint block (lines ~89-91):**
  - research_scheduler_main = _command_entrypoint("tools.cli.research_scheduler")
  - research_stats_main = _command_entrypoint("tools.cli.research_stats")
  - research_health_main = _command_entrypoint("tools.cli.research_health")

- **Routing dict (lines ~150-152):**
  - "research-scheduler": "research_scheduler_main"
  - "research-stats": "research_stats_main"
  - "research-health": "research_health_main"

- **Help text (lines ~211-213):**
  - "research-scheduler        Manage the RIS background ingestion scheduler"
  - "research-stats            Operator metrics snapshot and local-first export for RIS pipeline"
  - "research-health           Print RIS health status summary from stored run data"

### CLI Smoke Test Results

- `research-scheduler status --json`: OK — returned JSON array with 8 jobs. Verified: `JOB_REGISTRY: 8 jobs`
- `research-health --json`: OK — returned JSON with checks array (6 checks, all GREEN on empty log)
- `research-stats summary --json`: OK — returned JSON with generated_at, total_docs (5), total_claims (0), docs_by_family

### Tests Run and Results

| Test File | Passed | Failed | Skipped | Test Count (def test_) |
|-----------|--------|--------|---------|------------------------|
| tests/test_ris_scheduler.py | 31 | 0 | 0 | 31 |
| tests/test_ris_monitoring.py | 40 | 0 | 0 | 40 |
| tests/test_ris_ops_metrics.py | 21 | 0 | 0 | 21 |
| **Total** | **92** | **0** | **0** | **92** |

**Scheduler tests include run_log wiring tests (from plan 2ow):**
- test_run_job_writes_run_log_on_success (line 377)
- test_run_job_writes_run_log_on_error (line 399)
- test_run_job_to_health_end_to_end (line 421)

**Ops/metrics tests include CLI dispatch tests (from plan 2p9):**
- test_cli_summary_returns_0 (line 474)
- test_cli_summary_json_returns_valid_json (line 484)
- test_cli_export_writes_file (line 495)
- test_cli_missing_subcommand_returns_1 (line 507)
- test_cli_export_creates_parent_dirs (line 512)
- test_cli_summary_with_populated_data (line 522)

File line count: 551 lines (plan 2p9 required min_lines: 350 — already satisfied).

---

## GAPS OR MISMATCHES

### Gap 1: run_job() append_run wiring — CLOSED (already landed)

- **Expected by plan template:** Gap open, plan 2ow not yet executed.
- **Actual finding:** RESOLVED. The append_run wiring with injectable `_run_log_fn`, lazy import, and 3 dedicated scheduler tests are fully present in the codebase.
- **Evidence:** scheduler.py lines 293-306; test_ris_scheduler.py lines 377, 399, 421.
- **Status:** Plan 2ow is REDUNDANT — its deliverables are already in the codebase. Operator should mark 2ow as superseded or close it without execution.

### Gap 2: RIS_06 spec stale CLI command names — PARTIALLY CLOSED

- **Expected by plan template:** Stale "scheduler-status" and "research stats" in spec.
- **Actual finding in spec (docs/reference/RAGfiles/RIS_06_INFRASTRUCTURE.md):**
  - Lines 211-213: `python -m polytool research-stats summary [--json]` and `python -m polytool research-stats export [--out PATH]` — CORRECT with inline comment noting standalone command.
  - Lines 245-247: `python -m polytool research-scheduler status`, `research-scheduler status --json`, `research-scheduler start --dry-run` — CORRECT.
  - Lines 119-121: `research-scheduler status` and `research-scheduler run-job` references — CORRECT.
  - **Remaining gap:** `research-health` CLI is NOT listed anywhere in the spec's CLI reference section. The spec has no example for `python -m polytool research-health [--json]`. This is a doc-completeness gap but not a runtime error.
  - **Remaining gap:** Lines 171-184 still show old-style `polytool research ingest-all`, `polytool research ingest-academic` etc. — these are pre-RIS_06 command names that may not be shipped. Not verified in this pass.
- **Plan 2p9 scope:** Addresses spec CLI truth alignment and adds CLI tests. The CLI tests have already landed; the spec has partial fixes. Plan 2p9 should still execute to add the research-health CLI example to the spec.

### Gap 3: research-stats CLI has no CLI-level tests — CLOSED (already landed)

- **Expected by plan template:** Gap open, plan 2p9 not yet executed.
- **Actual finding:** RESOLVED. test_ris_ops_metrics.py has 6 CLI dispatch tests in a dedicated class (lines 474-522+). File is 551 lines (vs plan 2p9's min_lines: 350 requirement).
- **Status:** Plan 2p9 Task 2 (add CLI tests) is REDUNDANT. Only Task 1 (spec doc fixes) and Task 3 (dev log) remain meaningful.

---

## DEVIATIONS FROM PLAN

None — this was a read-only verification. The plan template anticipated Gaps 1 and 3 as open; they are in fact already closed. This means the verification outcome is VERIFIED rather than the expected PARTIAL verdict.

---

## RISK NOTES

1. **Vacuous GREEN is still a real operational risk (but wiring is now correct):** When no jobs have run, run_log.jsonl is empty and all health checks return GREEN with message "No run data available." This is expected behavior post-wiring. The first real scheduler invocation will produce RunRecord entries and enable real health evaluation. Operators should not interpret GREEN on an empty log as a healthy pipeline — they should check whether run_log.jsonl exists and has entries.

2. **model_unavailable check is a documented GREEN stub:** health_checks.py line 8 documents this explicitly. It always returns GREEN pending ProviderEvent data. This is expected, not a defect.

3. **rejection_audit_disagreement check may be data-starved:** This check requires audit runner output. If no audit runner has produced data, it returns vacuously GREEN. This is a known limitation at RIS_06 scope.

4. **APScheduler optional dependency:** start_research_scheduler() requires APScheduler ([ris] extras group). Without it, the import raises. JOB_REGISTRY and run_job() are importable without APScheduler (lazy import pattern). The spec notes this at line 119 but does not document the install command. Plan 2p9 should add the install note.

5. **research-health not in spec CLI reference:** The CLI is fully functional and registered, but docs/reference/RAGfiles/RIS_06_INFRASTRUCTURE.md has no example for `python -m polytool research-health [--json]`. This is a doc-completeness gap with no runtime impact.

6. **Plans 2ow and 2p9 status:** Both plan files exist at `.planning/quick/` but have no SUMMARY.md. Their deliverables are already in the codebase. Possible explanations: (a) another agent executed the work without going through the GSD plan system, or (b) the work was committed directly. Operator should close/archive 2ow and narrow 2p9 to spec doc updates only.

---

## Self-Check: PASSED

- SUMMARY.md created at correct path: `.planning/quick/260403-2pg-read-only-verification-of-ris-06-after-t/260403-2pg-SUMMARY.md`
- VERDICT present and set to VERIFIED
- Evidence table complete with all 11 file rows
- CLI wiring confirmed at all 3 locations in __main__.py
- Test counts from actual pytest output: 31 + 40 + 21 = 92 passed, 0 failed
- Gaps enumerated with open/closed status and file:line evidence
- Risk notes section present
- No production code modified
