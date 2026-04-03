# Dev Log — 2026-04-03: RIS R4 Monitoring and Health Checks

## Objective

Add operational visibility to the RIS pipeline: pipeline run logs, health condition
evaluation, alert routing abstraction, and a CLI health summary command. This
completes the RIS_06 monitoring layer so an operator can inspect pipeline health
without needing a Grafana dashboard or live Discord webhook.

Quick task: `260403-1sc` (Phase R4, monitoring/health side)

## Files Changed

**New files:**
- `packages/research/monitoring/__init__.py` — public API re-exports
- `packages/research/monitoring/run_log.py` — RunRecord dataclass + JSONL log functions
- `packages/research/monitoring/health_checks.py` — 6 health checks per RIS_06 spec
- `packages/research/monitoring/alert_sink.py` — LogSink + WebhookSink + fire_alerts
- `tools/cli/research_health.py` — CLI entrypoint for health summary
- `tests/test_ris_monitoring.py` — 40 deterministic offline tests
- `docs/features/FEATURE-ris-monitoring-health-v1.md` — feature documentation
- `docs/dev_logs/2026-04-03_ris_r4_monitoring_and_health.md` — this file

**Modified files:**
- `polytool/__main__.py` — registered `research-health` command
- `docs/CURRENT_STATE.md` — added monitoring/health section

## Implementation Notes

### Run Log Design

Followed the JSONL append-only pattern established by `precheck_ledger.py`. Key
decisions:

- `RunRecord` uses `__post_init__` to auto-derive `run_id` from sha256(pipeline+started_at)[:12]
  if not provided — no UUID dependency.
- `list_runs(window_hours=N)` filters on `started_at` ISO string comparison (UTC ISO-8601
  strings sort lexicographically, so this works without parsing).
- Returns newest-first by default — matches most operator use patterns (last run first).
- `DEFAULT_RUN_LOG_PATH = Path("artifacts/research/run_log.jsonl")` — separate from
  eval_artifacts to avoid coupling to evaluation layer.

### Health Check Design

6 checks implemented per RIS_06 spec table. Each check is a pure function that
takes the filtered run list and returns a HealthCheckResult:

1. **pipeline_failed** — scans the runs list for any `exit_status == "error"`. RED
   on first match. Key: checks are already newest-first so the most recent error is
   found first.

2. **no_new_docs_48h** — sums `accepted` across all provided runs. YELLOW when runs
   exist but sum is 0. GREEN when no runs (insufficient data is not an alert condition).

3. **accept_rate_low** — `accepted / (accepted+rejected)`. YELLOW when rate < 30% AND
   total > 5. The minimum-5 threshold avoids false positives on first-run or sparse
   periods.

4. **accept_rate_high** — YELLOW when rate > 90% AND total > 10. Signals potential
   gate miscalibration (accepting too much). Higher threshold (10) because high volume
   is required for this signal to be meaningful.

5. **model_unavailable** — always GREEN in this pass. Deferred until scheduler wires
   provider error events.

6. **rejection_audit_disagreement** — takes an optional `audit_disagreement_rate` kwarg.
   GREEN when None (no audit data available). YELLOW when rate > 30%.

### Alert Sink Design

Simple Protocol-based abstraction. `LogSink` is the zero-config default — writes to
`logging.getLogger("ris.alerts")` at WARNING (YELLOW) or ERROR (RED) level.

`WebhookSink` uses lazy `import requests` inside `fire()` to keep it optional.
Matches the pattern from `packages/polymarket/notifications/discord.py`.

`fire_alerts()` is a simple filter loop: skip GREEN, call `sink.fire()` for YELLOW/RED,
return count.

### CLI Design

`research_health.main(argv)` follows the exact pattern of `research_ingest.main()`:
- argparse with explicit help
- graceful empty list on missing log file
- `--json` flag for machine-readable output
- always returns 0 (informational, cron-safe)
- `LogSink` for alert emission (no network calls)

JSON `summary` field uses `"no_data"` when no runs exist (avoids misleading "GREEN"
when there's simply no data yet).

## Test Results

```
tests/test_ris_monitoring.py — 40 passed, 0 failed
```

```
Full regression suite — 3555 passed, 2 failed (pre-existing from scheduler agent work), 0 new failures
```

Note: The 2 scheduler failures (`test_ris_scheduler.py`) were pre-existing from another
concurrent agent's uncommitted work. Verified by stash test: 0 failures on the stashed
state using the same scheduler test file.

## Health Checks Implemented

| Check                          | Level  | Condition                                              |
|--------------------------------|--------|--------------------------------------------------------|
| `pipeline_failed`              | RED    | exit_status == "error" in any run                      |
| `no_new_docs_48h`              | YELLOW | runs exist but accepted == 0 across window              |
| `accept_rate_low`              | YELLOW | accept rate < 30%, total > 5                           |
| `accept_rate_high`             | YELLOW | accept rate > 90%, total > 10                          |
| `model_unavailable`            | GREEN  | stub — no provider event data wired yet                |
| `rejection_audit_disagreement` | YELLOW | audit_disagreement_rate > 30% (requires audit runner)  |

## CLI Commands Verified

```bash
python -m polytool research-health --help      # help text, exit 0
python -m polytool research-health              # "No run data" message, exit 0
python -m polytool research-health --json       # {"checks":[...],"summary":"no_data","run_count":0}
python -m polytool --help | grep research-health  # appears in command list
```

## Alert Sink Behavior

- `LogSink` is the default and only sink that runs in CI/tests
- `WebhookSink` is instantiated only when explicitly configured with a URL
- No test ever instantiates `WebhookSink` without mocking `requests.post`
- `fire_alerts()` skips GREEN, fires YELLOW+RED, returns count

## Remaining Ops Gaps

The following are intentionally out of scope and tracked for future plans:

1. ClickHouse `ingestion_log` table — real-time Grafana health dashboards
2. Grafana panels — trend graphs for accept rate, error rate, run frequency
3. APScheduler wiring — automatic `append_run()` in the scheduler's run loop
4. `model_unavailable` check — requires provider error event data from scheduler
5. Rejection audit wiring — requires audit runner that computes disagreement rate

## Codex Review Note

Tier: Skip (no execution/kill-switch/order-placement code). No review required.
