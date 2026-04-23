# WP4-B: n8n Execution Metrics Collector Workflow

**Date:** 2026-04-23
**Work packet:** WP4-B (RIS Phase 2A monitoring infrastructure)
**Lane:** n8n workflow lane; runs separate from ris-unified-dev.json

---

## What Changed and Why

**Created:** `infra/n8n/workflows/ris-n8n-metrics-collector.json`

WP4-B delivers the hourly metrics collector that feeds the `polytool.n8n_execution_metrics`
table created in WP4-A. It is a standalone workflow — entirely separate from
`ris-unified-dev.json` — so it can be imported, activated, and troubleshot independently
of the main RIS pipeline.

---

## Final Workflow Shape

```
Schedule: Every Hour
  └─► API: GET Executions           GET http://localhost:5678/api/v1/executions
        └─► Transform: To ClickHouse Rows   Code node (JS)
              └─► ClickHouse: INSERT Rows   POST http://clickhouse:8123/ FORMAT JSONEachRow
```

**Four nodes, linear flow, no branches.**

| Node | Type | Role |
|------|------|------|
| `Schedule: Every Hour` | `scheduleTrigger` v1 | Fires once per hour |
| `API: GET Executions` | `httpRequest` v4.2 | Fetches last 250 executions from n8n REST API |
| `Transform: To ClickHouse Rows` | `code` v2 | Maps API response to WP4-A schema; builds JSONL body |
| `ClickHouse: INSERT Rows` | `httpRequest` v4.2 | POSTs JSONL to ClickHouse HTTP interface |

---

## Mapping to WP4-A DDL

| ClickHouse column | n8n API field | Transform note |
|-------------------|---------------|----------------|
| `execution_id` | `exec.id` | `String(exec.id)` |
| `workflow_id` | `exec.workflowId` | `String(exec.workflowId)` |
| `workflow_name` | `exec.workflowName` | String passthrough |
| `status` | `exec.status` | String passthrough |
| `mode` | `exec.mode` | String passthrough |
| `started_at` | `exec.startedAt` | ISO→`YYYY-MM-DD HH:MM:SS` UTC via `toClickHouseDT()` |
| `stopped_at` | `exec.stoppedAt` | Same conversion; `null` while running |
| `duration_seconds` | computed | `(stoppedAt - startedAt) / 1000`; `null` while running |
| `collected_at` | — | Omitted; ClickHouse `DEFAULT now()` applies |

**Idempotency:** `collected_at` is the version column for `ReplacingMergeTree(collected_at)`.
Each hourly run re-fetches any execution that was `running` at the previous pass and writes
a newer row. ClickHouse collapses duplicates at merge time, keeping the latest. No dedup
logic needed in the collector.

---

## Design Decisions

**No pagination.** `limit=250` covers any realistic hourly execution volume for a 5–10-workflow
RIS instance. Pagination via `nextCursor` is left as a future enhancement if the system
grows beyond ~250 executions/hour.

**No IF branch.** If there are zero executions (e.g., n8n just started), the transform returns
`clickhouse_body: ""`. ClickHouse accepts an empty INSERT with `FORMAT JSONEachRow` and returns
`Ok.` with HTTP 200. The workflow completes cleanly. No skip logic needed.

**`active: false` on import.** The workflow ships disabled. The operator activates it after
verifying that the required environment variables are set (see Pre-Activation Checklist below).

**ClickHouse user hardcoded as `polytool_admin`.** The username is not a secret. The password
comes from `$env.CLICKHOUSE_PASSWORD` (n8n runtime environment variable), following the
ClickHouse auth rule in CLAUDE.md.

**n8n API URL uses `localhost`.** From within the n8n container, `localhost:5678` reaches
n8n's own API. The Docker network service name `n8n` would not resolve from inside the same
container. `localhost` is the correct address here.

**ClickHouse URL uses service name `clickhouse`.** From within the n8n container, the Docker
Compose service name `clickhouse` resolves to the ClickHouse container on the `polytool`
network. Both services share that network per `docker-compose.yml`.

---

## Pre-Activation Checklist

Before running `n8n_import` and activating this workflow, ensure:

1. **`CLICKHOUSE_PASSWORD`** is available in the n8n container environment.
   Add to the `n8n` service in `docker-compose.yml`:
   ```yaml
   - CLICKHOUSE_PASSWORD=${CLICKHOUSE_PASSWORD}
   ```

2. **`N8N_API_KEY`** is set with a valid n8n API key (generate from n8n UI → Settings → API).
   Add to the `n8n` service:
   ```yaml
   - N8N_API_KEY=${N8N_API_KEY}
   ```

3. **WP4-A DDL applied** — `polytool.n8n_execution_metrics` table exists in ClickHouse.
   Verified on next `docker compose up` or via:
   ```
   curl "http://localhost:8123/?query=SELECT+1+FROM+polytool.n8n_execution_metrics+LIMIT+1"
   ```

4. Import the workflow via the existing importer (after adding to `CANONICAL_WORKFLOWS`):
   ```
   python infra/n8n/import_workflows.py --no-activate
   ```
   Then activate from the n8n UI after confirming env vars are present.

---

## Import Script Note

`infra/n8n/import_workflows.py` has a `CANONICAL_WORKFLOWS` list that controls which
workflows are managed by the importer. WP4-B does **not** modify that file (outside the
scope of this work packet). To include this workflow in automated import, a future step adds:

```python
("METRICS_COLLECTOR_ID", "ris-n8n-metrics-collector.json"),
```

to `CANONICAL_WORKFLOWS`. Until then, the workflow can be imported manually via the n8n UI
(Settings → Import Workflow → select the JSON file).

---

## Commands Run / Validation Results

```
python -m polytool --help
```
**Result:** CLI loads cleanly. No import errors. Workflow file is static JSON with no Python
import path. CLI smoke test confirms the repo is healthy after file creation.

```
python -c "import json; json.load(open('infra/n8n/workflows/ris-n8n-metrics-collector.json'))"
```
**Result:** JSON parses without error.
- Workflow name: `RIS -- n8n Execution Metrics Collector`
- 4 nodes extracted: `Schedule: Every Hour`, `API: GET Executions`,
  `Transform: To ClickHouse Rows`, `ClickHouse: INSERT Rows`
- 3 connection entries: all 4 nodes chained in linear order

```
node --check wp4b_check.js   (jsCode extracted from JSON, written to temp file)
```
**Result:** `JS syntax OK` — Node.js v24.11.1 reports no syntax errors in the transform code.

---

## What Remains for WP4-C and WP4-D

| Item | Work packet | What it builds |
|------|-------------|----------------|
| Grafana RIS dashboard | WP4-C | `infra/grafana/dashboards/ris-pipeline-health.json`. Four panels: success rate (time series), avg duration (time series), failure frequency by workflow (bar chart), last run status (table with green/red value mappings via `argMax`-based queries using `FINAL`). |
| Stale pipeline alert | WP4-D | Grafana alert rule: `max(started_at) WHERE status='success'` per `workflow_name`. Fires when age > 6 hours. Configure "No Data" state → Alerting. |
| Import script update | (cleanup) | Add `METRICS_COLLECTOR_ID` entry to `CANONICAL_WORKFLOWS` in `infra/n8n/import_workflows.py`. |
| docker-compose env vars | (cleanup) | Add `CLICKHOUSE_PASSWORD` and `N8N_API_KEY` to the `n8n` service environment in `docker-compose.yml`. |

WP4-A and WP4-B are complete. WP4-C and WP4-D build on this workflow's output without
modifying it.

---

**Codex review tier:** Skip (n8n workflow JSON + infra config — matches repo Codex policy
exclusion for infra config files).
