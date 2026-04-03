---
phase: quick-260403-1sc
plan: 01
subsystem: research/monitoring
tags: [ris, monitoring, health-checks, alert-sink, cli]
dependency_graph:
  requires: [packages/research/monitoring, packages/research/evaluation/artifacts]
  provides: [packages/research/monitoring, tools/cli/research_health]
  affects: [polytool/__main__.py, docs/CURRENT_STATE.md]
tech_stack:
  added: [JSONL run log, health checks, alert sink abstraction]
  patterns: [TDD, JSONL append-only log, Protocol-based alert sink, argparse CLI]
key_files:
  created:
    - packages/research/monitoring/__init__.py
    - packages/research/monitoring/run_log.py
    - packages/research/monitoring/health_checks.py
    - packages/research/monitoring/alert_sink.py
    - tools/cli/research_health.py
    - tests/test_ris_monitoring.py
    - docs/features/FEATURE-ris-monitoring-health-v1.md
    - docs/dev_logs/2026-04-03_ris_r4_monitoring_and_health.md
  modified:
    - polytool/__main__.py
    - docs/CURRENT_STATE.md
decisions:
  - "RunRecord auto-derives run_id from sha256(pipeline+started_at)[:12] — no UUID dependency"
  - "LogSink is the zero-config default; WebhookSink is opt-in with lazy requests import"
  - "fire_alerts returns count (not list) to keep the return type simple for caller use"
  - "CLI always exits 0 — health output is informational, non-zero would break cron"
  - "model_unavailable check is GREEN stub — deferred until scheduler wires provider events"
  - "accept_rate_low requires total > 5, accept_rate_high requires total > 10 — avoids false positives on sparse runs"
metrics:
  duration_minutes: 9
  completed_date: "2026-04-03"
  tasks_completed: 2
  tests_added: 40
  files_created: 8
  files_modified: 2
---

# Phase quick-260403-1sc Plan 01: RIS Monitoring and Health Checks Summary

**One-liner:** JSONL pipeline run log + 6 RIS_06 health checks + LogSink/WebhookSink alert routing + `research-health` CLI

## What Was Built

RIS operational visibility layer (R4 of RIS_06 plan). An operator can now inspect
whether the RIS pipeline is healthy by running `python -m polytool research-health`.
No dashboard, no Discord webhook, no environment variables required.

### Core modules

**`packages/research/monitoring/run_log.py`**
- `RunRecord` dataclass with auto-derived `run_id` (sha256[:12] of pipeline+started_at)
- `append_run(record, path)` — creates parent dirs, appends JSONL, never overwrites
- `list_runs(path, window_hours)` — reads all records, optional window filter, newest-first
- `load_last_run(path)` — returns most recent RunRecord or None

**`packages/research/monitoring/health_checks.py`**
- `HealthCheckResult(check_name, status, message, data)` dataclass
- `HealthCheck(name, description)` descriptor dataclass
- `ALL_CHECKS` — list of 6 HealthCheck instances
- `evaluate_health(runs, window_hours, audit_disagreement_rate)` — returns list[HealthCheckResult]

**`packages/research/monitoring/alert_sink.py`**
- `AlertSink` — Protocol for alert routing adapters
- `LogSink` — default, writes to `ris.alerts` logger, always returns True, no network
- `WebhookSink(webhook_url)` — optional, POSTs JSON, lazy `requests` import
- `fire_alerts(results, sink, min_level)` — skips GREEN, fires YELLOW/RED, returns count

**`tools/cli/research_health.py`**
- `main(argv) -> int` — always returns 0
- `--json` flag for JSON output with `{"checks": [...], "summary": "...", "run_count": N}`
- `--window-hours N` (default 48)
- `--run-log PATH`, `--eval-artifacts PATH` (reserved)

### The 6 Health Checks

| Check                          | Level  | Condition                                              |
|--------------------------------|--------|--------------------------------------------------------|
| `pipeline_failed`              | RED    | Any run in window has `exit_status == "error"`         |
| `no_new_docs_48h`              | YELLOW | Runs exist but total accepted == 0                     |
| `accept_rate_low`              | YELLOW | accept rate < 30%, total > 5                           |
| `accept_rate_high`             | YELLOW | accept rate > 90%, total > 10                          |
| `model_unavailable`            | GREEN  | Stub — deferred to scheduler integration               |
| `rejection_audit_disagreement` | YELLOW | audit_disagreement_rate > 30% (requires audit runner)  |

All checks return GREEN when no runs are provided (no data = no signal).

## Test Results

```
tests/test_ris_monitoring.py — 40 passed, 0 failed (>= 20 required)
Full regression suite — 3555 passed, 2 pre-existing failures (unrelated scheduler tests)
```

The 2 pre-existing failures in `test_ris_scheduler.py` are from another concurrent agent's
uncommitted work. Verified: the test file passes when stashed state is tested in isolation.

## Verification

All success criteria met:
- [x] `packages/research/monitoring/` exists with all 4 files
- [x] 6 health checks implemented per spec
- [x] LogSink (default, log-only), WebhookSink (optional, never required in tests)
- [x] CLI `research-health` registered and functional (`--json`, `--window-hours`)
- [x] 40 deterministic offline tests, all passing
- [x] Full test suite regression: no new failures
- [x] Feature doc + mandatory dev log created
- [x] CURRENT_STATE.md updated

## Commits

| Task | Commit | Description                                                      |
|------|--------|------------------------------------------------------------------|
| 1    | 7c0ca91 | feat(quick-260403-1sc-01): add RIS monitoring module             |
| 2    | 9d5ffc6 | feat(quick-260403-1sc-02): add research-health CLI, docs, state  |

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

- `model_unavailable` check always returns GREEN. This is intentional: the check is
  explicitly listed as "GREEN stub — deferred" in the RIS_06 spec. Future scheduler
  wiring will provide provider error event data. Tracked in FEATURE doc and dev log.

## Self-Check: PASSED
