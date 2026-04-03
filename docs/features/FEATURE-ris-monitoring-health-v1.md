# RIS Monitoring and Health Checks v1

## Overview

Operational visibility layer for the Research Intelligence System (RIS). Provides
pipeline run logs, health condition evaluation, and alert routing so an operator
can inspect whether the RIS pipeline is healthy without needing a dashboard or
live Discord webhook.

This is part of the RIS_06 infrastructure plan (Phase R4 operational layer).

## Module Location

```
packages/research/monitoring/
  __init__.py       Public API re-exports
  run_log.py        JSONL pipeline run log
  health_checks.py  Health condition evaluators
  alert_sink.py     Alert routing abstraction
```

## Run Log (`run_log.py`)

Append-only JSONL log of each RIS pipeline execution.

**Default path:** `artifacts/research/run_log.jsonl`

**Schema version:** `run_log_v1`

### RunRecord fields

| Field          | Type                        | Description                              |
|----------------|-----------------------------|------------------------------------------|
| `run_id`       | str (12-char sha256 prefix) | Auto-derived from pipeline+started_at    |
| `pipeline`     | str                         | Pipeline name (e.g. "ris_ingest")        |
| `started_at`   | ISO-8601 UTC str            | Run start timestamp                      |
| `duration_s`   | float                       | Elapsed seconds                          |
| `accepted`     | int                         | Documents accepted this run              |
| `rejected`     | int                         | Documents rejected this run              |
| `errors`       | int                         | Hard errors encountered                  |
| `exit_status`  | "ok"\|"error"\|"partial"     | Final run outcome                        |
| `metadata`     | dict                        | Free-form extra data                     |
| `schema_version` | str                       | Always "run_log_v1"                      |

### Functions

```python
from packages.research.monitoring import append_run, list_runs, load_last_run, RunRecord

# Log a run
rec = RunRecord(pipeline="ris_ingest", started_at="...", duration_s=1.5,
                accepted=5, rejected=2, errors=0, exit_status="ok")
append_run(rec)

# Read back (newest first, optional window filter)
runs = list_runs(window_hours=48)
last = load_last_run()
```

## Health Checks (`health_checks.py`)

Implements the RIS_06 health check table. Returns a list of `HealthCheckResult`
objects, one per check.

### The 6 Health Checks

| Check Name                     | Level  | Condition                                                    |
|--------------------------------|--------|--------------------------------------------------------------|
| `pipeline_failed`              | RED    | Any run in window has `exit_status == "error"`               |
| `no_new_docs_48h`              | YELLOW | Runs exist but total `accepted == 0` across window            |
| `accept_rate_low`              | YELLOW | `accepted / (accepted+rejected) < 0.30` AND total > 5       |
| `accept_rate_high`             | YELLOW | `accepted / (accepted+rejected) > 0.90` AND total > 10      |
| `model_unavailable`            | GREEN  | Stub — deferred until provider event data is wired           |
| `rejection_audit_disagreement` | YELLOW | `audit_disagreement_rate > 0.30` (requires audit runner)     |

All checks return GREEN when there are no runs (insufficient data = no signal).

### Usage

```python
from packages.research.monitoring import evaluate_health, list_runs

runs = list_runs(window_hours=48)
results = evaluate_health(runs, window_hours=48)

for r in results:
    print(f"{r.check_name}: {r.status} — {r.message}")
```

### HealthCheckResult fields

| Field        | Type           | Description                             |
|--------------|----------------|-----------------------------------------|
| `check_name` | str            | Check identifier                        |
| `status`     | GREEN/YELLOW/RED | Health verdict                        |
| `message`    | str            | Human-readable explanation              |
| `data`       | dict           | Supporting data for the verdict         |

## Alert Sink (`alert_sink.py`)

Abstract routing layer for health alerts. Two implementations provided.

### LogSink (default, no config required)

Writes YELLOW results at WARNING level and RED results at ERROR level to
the `ris.alerts` logger. Never makes network calls. Always returns True.

```python
from packages.research.monitoring import LogSink, fire_alerts

sink = LogSink()
count = fire_alerts(results, sink)  # count = number of YELLOW/RED alerts fired
```

### WebhookSink (optional, needs URL)

POSTs a JSON payload to a webhook URL on YELLOW/RED alerts. Designed for
Discord incoming webhooks or generic HTTP endpoints. The `requests` library is
imported lazily — not a hard dependency.

```python
from packages.research.monitoring import WebhookSink, fire_alerts

sink = WebhookSink(webhook_url="https://discord.com/api/webhooks/...")
count = fire_alerts(results, sink)
```

WebhookSink is NEVER instantiated in automated tests — all tests use LogSink
or a mock, ensuring zero network calls in the test suite.

### fire_alerts behavior

- Skips GREEN results entirely
- Calls `sink.fire(result)` for each YELLOW or RED result
- Returns count of alerts fired

## CLI: research-health

```bash
# Human-readable health table (default 48h window)
python -m polytool research-health

# JSON output
python -m polytool research-health --json

# Custom window
python -m polytool research-health --window-hours 24

# Custom log path
python -m polytool research-health --run-log artifacts/research/run_log.jsonl
```

### Human-readable output (example)

```
RIS Health Summary (48h window, 3 runs) -- GREEN

CHECK                                    STATUS   MESSAGE
----------------------------------------------------------------------
pipeline_failed                          GREEN    No pipeline errors detected.
no_new_docs_48h                          GREEN    12 document(s) accepted in the monitored window.
accept_rate_low                          GREEN    Accept rate is healthy: 52.2% (12/23).
accept_rate_high                         GREEN    Accept rate is 52.2% (12/23) — within expected bounds.
model_unavailable                        GREEN    Model availability monitoring not yet wired...
rejection_audit_disagreement             GREEN    No audit disagreement data provided.
```

### JSON output shape

```json
{
  "checks": [
    {
      "check_name": "pipeline_failed",
      "status": "GREEN",
      "message": "No pipeline errors detected.",
      "data": {}
    }
  ],
  "summary": "GREEN",
  "run_count": 3
}
```

`summary` values: `"GREEN"`, `"YELLOW"`, `"RED"`, `"no_data"` (when no runs).

The CLI always exits 0 — health output is informational; non-zero would break cron.

## Wiring the Run Log from a Pipeline

The following pipelines automatically call `append_run()` — operators do not need
to wire this manually:

| Command                       | Pipeline Name           | When Written                                    |
|-------------------------------|-------------------------|-------------------------------------------------|
| `research-ingest`             | `research_ingest`       | After every ingest (success, rejection, or error)|
| `research-acquire`            | `research_acquire`      | After every acquire (skipped on `--dry-run`)     |
| `research-acquire --search`   | `research_acquire_search`| After search+multi-ingest (planned)             |
| `research-scheduler run-job`  | `{job_id}`              | After every scheduled job                       |

The `--run-log PATH` flag controls where the JSONL is written (default:
`artifacts/research/run_log.jsonl`). All CLI commands accept this override.

### Manual wiring for custom pipelines

To integrate the run log with a custom pipeline, use this pattern (same as the
scheduler and CLI entrypoints):

```python
import time
from packages.research.monitoring import RunRecord, append_run

start = time.monotonic()
# ... pipeline logic ...
duration = time.monotonic() - start

from datetime import datetime, timezone
rec = RunRecord(
    pipeline="ris_ingest",
    started_at=datetime.now(timezone.utc).isoformat(),
    duration_s=duration,
    accepted=result.accepted_count,
    rejected=result.rejected_count,
    errors=result.error_count,
    exit_status="ok" if result.error_count == 0 else "partial",
)
append_run(rec)
```

## Deferred Items

The following items are intentionally out of scope for this plan and tracked
for future implementation:

1. **ClickHouse `ingestion_log` table** — For real-time Grafana dashboards; deferred to
   RIS_06 infrastructure plan (ClickHouse write path).
2. **Grafana panels** — Health check trend panels and alert history; requires CH table first.
3. **`model_unavailable` check** — Requires provider event data (e.g. 503 counts from
   the evaluation provider); deferred until scheduler wires provider error events.
   Currently labeled `[DEFERRED]` in output.
4. **Rejection audit wiring** — `rejection_audit_disagreement` requires an audit runner
   that computes disagreement rate; deferred to audit tooling plan.
   Currently labeled `[DEFERRED]` in output.

**Completed (no longer deferred):**
- Manual CLI wiring: `research-ingest` and `research-acquire` now call `append_run()` automatically.
- APScheduler wiring: scheduler `run_job()` calls `append_run()` (completed in quick-260403-2ow).

## Tests

54 deterministic offline tests in `tests/test_ris_monitoring.py`.

- `TestRunLog` (9 tests): append/list/load lifecycle, window filtering, newest-first ordering
- `TestHealthChecks` (17 tests): all 6 checks, boundary conditions, empty-run cases
- `TestAlertSink` (7 tests): LogSink, WebhookSink (mocked), fire_alerts GREEN skip
- `TestMonitoringInit` (1 test): public API completeness
- `TestResearchHealthCLI` (6 tests): no-data path, JSON output, RED detection, window filtering, no-network
- `TestCLIRunLogWiring` (6 tests): research-ingest and research-acquire append_run() integration
- `TestHealthTruthfulness` (5 tests): [DEFERRED] labeling for stub checks
- `TestIntegrationIngestToHealth` (3 tests): end-to-end file ingest -> run_log -> health pipeline

All tests are fully offline. No network calls. No ClickHouse required.
No environment variables required.
