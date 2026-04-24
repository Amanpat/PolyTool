# WP4-C: RIS Pipeline Health — Grafana Dashboard

**Date:** 2026-04-23
**Work packet:** WP4-C (RIS Phase 2A monitoring infrastructure)
**Lane:** Grafana dashboard only; WP4-A DDL and WP4-B collector are prerequisites (both complete)

---

## What Changed and Why

**Created:** `infra/grafana/dashboards/ris-pipeline-health.json`

WP4-C delivers the Grafana dashboard that makes the `polytool.n8n_execution_metrics` table
visible to operators. Without this dashboard, the WP4-A/WP4-B stack collects data silently
with no human-readable view. The four panels cover the core health questions for a 5–10-workflow
RIS instance: is it succeeding, how fast, where are failures concentrating, and what ran most
recently?

---

## Conventions Followed (no assumptions required)

All conventions were read directly from the existing `infra/grafana/` surface before writing.

| Convention | Source | Applied value |
|------------|---------|---------------|
| Datasource UID | `provisioning/datasources/clickhouse.yaml` | `clickhouse-polytool` |
| Datasource type | All existing dashboards | `grafana-clickhouse-datasource` |
| Schema version | All existing dashboards | 39 |
| Plugin version | All existing dashboards | `11.4.0` |
| `editorType` | All existing dashboards | `sql` |
| `format` | All existing dashboards | `1` |
| Tag prefix | All existing dashboards | `polytool` |
| Dashboard UID pattern | All existing dashboards | `polytool-<slug>` |
| Timeseries `queryType` | `polyttool_strategy_detectors.json`, `polyttool_pnl.json` | `timeseries` |
| Table/other `queryType` | `polyttool_crypto_pair_paper_soak.json` | `sql` |
| `id: null` | All existing dashboards | preserved for Grafana to assign on import |
| Folder | `provisioning/dashboards/dashboards.yaml` | empty (flat folder, all dashboards in `/var/lib/grafana/dashboards`) |

---

## Final Panel List

| # | Title | Type | gridPos | Query table |
|---|-------|------|---------|-------------|
| 1 | Execution Success Rate | `timeseries` | y=0, x=0, w=12, h=9 | `n8n_execution_metrics FINAL` |
| 2 | Avg Execution Duration (Successful Runs) | `timeseries` | y=0, x=12, w=12, h=9 | `n8n_execution_metrics FINAL` |
| 3 | Failure Count by Workflow | `barchart` | y=9, x=0, w=24, h=8 | `n8n_execution_metrics FINAL` |
| 4 | Latest Run Status per Workflow | `table` | y=17, x=0, w=24, h=9 | `n8n_execution_metrics FINAL` |

All panels use datasource UID `clickhouse-polytool`. All queries use `FINAL` to read collapsed
state from the `ReplacingMergeTree(collected_at)` engine (required — without FINAL, duplicate
`execution_id` rows from multi-pass collection would inflate counts).

---

## Query Shape Summary

**Panel 1 — Execution Success Rate (timeseries)**
```sql
SELECT
  toStartOfHour(started_at) AS time,
  round(
    countIf(status = 'success') * 100.0 / count(),
    1
  ) AS success_rate_pct
FROM polytool.n8n_execution_metrics FINAL
WHERE $__timeFilter(started_at)
GROUP BY time
ORDER BY time
```
- Buckets hourly; countIf/count gives 0–100 percentage value.
- Unit: `percent` (Grafana 0–100 scale); hard min=0, max=100.
- `$__timeFilter(started_at)` respects the Grafana time picker.

**Panel 2 — Avg Duration (timeseries)**
```sql
SELECT
  toStartOfHour(started_at) AS time,
  round(avg(duration_seconds), 1) AS avg_duration_sec
FROM polytool.n8n_execution_metrics FINAL
WHERE $__timeFilter(started_at)
  AND status = 'success'
  AND duration_seconds IS NOT NULL
GROUP BY time
ORDER BY time
```
- Filters to successful runs only; excludes null durations (still-running executions).
- Unit: `s` (seconds); min=0.

**Panel 3 — Failure Count by Workflow (barchart)**
```sql
SELECT
  workflow_name,
  countIf(status IN ('error', 'crashed')) AS failure_count
FROM polytool.n8n_execution_metrics FINAL
WHERE $__timeFilter(started_at)
GROUP BY workflow_name
ORDER BY failure_count DESC
```
- Covers both `error` and `crashed` status values from the WP4-A schema.
- Bar threshold: green at 0, red at ≥ 1 — bars turn red as soon as any failures exist.

**Panel 4 — Latest Run Status per Workflow (table)**
```sql
SELECT
  workflow_name,
  argMax(status, started_at)                      AS last_status,
  max(started_at)                                  AS last_run_at,
  round(argMax(duration_seconds, started_at), 1)  AS last_duration_sec
FROM polytool.n8n_execution_metrics FINAL
WHERE started_at >= now() - INTERVAL 7 DAY
GROUP BY workflow_name
ORDER BY last_run_at DESC
```
- Uses `argMax(status, started_at)` to get the status of the most recent execution per
  workflow, consistent with the `ReplacingMergeTree` intent.
- Fixed 7-day lookback (independent of time picker) so operators always see pipeline status
  even when the time picker is zoomed in to a narrow window.
- `last_status` column has Grafana value mappings:
  `success` → green, `error` → red, `crashed` → dark-red, `running` → blue,
  `waiting` → yellow, `canceled` → gray.

---

## Commands Run / Validation Results

```
python -m polytool --help
```
**Result:** CLI loads cleanly. No import errors.

```
python -c "import json; d=json.load(open('infra/grafana/dashboards/ris-pipeline-health.json')); ..."
```
**Result:**
```
JSON: valid
Title: PolyTool - RIS Pipeline Health
UID: polytool-ris-pipeline-health
SchemaVersion: 39
Tags: ['polytool', 'ris', 'n8n']
Refresh: 1m
Panel count: 4
  [1] Execution Success Rate | type=timeseries | queryType=timeseries | gridPos={'h': 9, 'w': 12, 'x': 0, 'y': 0}
  [2] Avg Execution Duration (Successful Runs) | type=timeseries | queryType=timeseries | gridPos={'h': 9, 'w': 12, 'x': 12, 'y': 0}
  [3] Failure Count by Workflow | type=barchart | queryType=sql | gridPos={'h': 8, 'w': 24, 'x': 0, 'y': 9}
  [4] Latest Run Status per Workflow | type=table | queryType=sql | gridPos={'h': 9, 'w': 24, 'x': 0, 'y': 17}
Datasource UIDs: all panels → clickhouse-polytool
```

No SQL linter is configured in this repo (same situation as WP4-A). Queries were reviewed
manually against the WP4-A DDL column list and checked for correct `FINAL` usage.

---

## Import Instructions

The provisioning layer (`provisioning/dashboards/dashboards.yaml`) watches
`/var/lib/grafana/dashboards` and picks up all JSON files automatically. The dashboard
will appear after the next Grafana restart or provisioning refresh cycle — no manual
import step is needed if Docker Compose mounts the `infra/grafana/dashboards/` directory
at that path.

For manual import (Grafana UI): Dashboards → Import → Upload JSON file →
select `infra/grafana/dashboards/ris-pipeline-health.json`.

---

## What Remains for WP4-D

| Item | Work packet | What it builds |
|------|-------------|----------------|
| Stale pipeline alert | WP4-D | Grafana alert rule: `max(started_at) WHERE status='success'` per `workflow_name`. Fires when last success age > 6 hours. Configure "No Data" state → Alerting. Separate from this dashboard file — add as a Grafana alert rule JSON or via UI. |

WP4-A, WP4-B, and WP4-C are complete. WP4-D is the only remaining RIS Phase 2A
monitoring work packet.

---

**Codex review tier:** Skip (Grafana dashboard JSON — matches repo Codex policy exclusion
for infra config files).
