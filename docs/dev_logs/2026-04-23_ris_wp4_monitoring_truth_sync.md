# RIS Phase 2A — Monitoring Truth-Sync Pass

**Date:** 2026-04-23
**Scope:** Read-only consistency check of the WP4-A/B/C monitoring lane
**Mutations:** None — lane is internally consistent; no code changes required

---

## Objective

Verify that the monitoring surfaces landed in WP4-A (DDL), WP4-B (collector + activation
plumbing), and WP4-C (Grafana dashboard) are internally consistent on:
- table name and column names
- collector field mapping
- dashboard queries and datasource assumptions
- workflow file names and canonical import registration
- environment variable wiring

---

## Files Inspected

| File | Role |
|------|------|
| `infra/clickhouse/initdb/28_n8n_execution_metrics.sql` | WP4-A DDL — table definition, engine, TTL, grant |
| `infra/n8n/workflows/ris-n8n-metrics-collector.json` | WP4-B workflow — INSERT target, field mapping, env var reads |
| `infra/grafana/dashboards/ris-pipeline-health.json` | WP4-C dashboard — panel queries, datasource UID |
| `infra/grafana/provisioning/datasources/clickhouse.yaml` | Grafana datasource — UID source of truth |
| `infra/grafana/provisioning/dashboards/dashboards.yaml` | Grafana provisioning — watched directory |
| `infra/n8n/import_workflows.py` | Import script — CANONICAL_WORKFLOWS list |
| `docker-compose.yml` (n8n service block) | Env var passthrough for collector runtime |
| `.env.example` (n8n section) | Operator documentation of N8N_API_KEY |

Dev logs cross-referenced:
- `docs/dev_logs/2026-04-23_ris_wp4a_clickhouse_ddl.md`
- `docs/dev_logs/2026-04-23_ris_wp4b_metrics_collector.md`
- `docs/dev_logs/2026-04-23_ris_wp4b_activation_plumbing.md`
- `docs/dev_logs/2026-04-23_ris_wp4c_grafana_dashboard.md`
- `docs/dev_logs/2026-04-23_ris_parallel_wp4c_wp4bactivate_codex_verification.md`

---

## Cross-Check Matrix

### Table name

| Surface | Value | Match |
|---------|-------|-------|
| DDL `CREATE TABLE` | `polytool.n8n_execution_metrics` | — |
| Collector INSERT query | `INSERT INTO polytool.n8n_execution_metrics FORMAT JSONEachRow` | ✅ |
| Dashboard panel 1–4 (rawSql) | `FROM polytool.n8n_execution_metrics FINAL` | ✅ |

### Column names (DDL → collector output → dashboard queries)

| DDL column | Collector output field | Dashboard references | Match |
|------------|------------------------|----------------------|-------|
| `execution_id` | `execution_id` | not queried directly | ✅ |
| `workflow_id` | `workflow_id` | not queried directly | ✅ |
| `workflow_name` | `workflow_name` | `GROUP BY workflow_name`, `argMax(...)` | ✅ |
| `status` | `status` | `countIf(status = 'success')`, `status IN (...)`, `argMax(status, ...)` | ✅ |
| `mode` | `mode` | not queried (telemetry only) | ✅ |
| `started_at` | `started_at` | `$__timeFilter(started_at)`, `toStartOfHour(started_at)`, `max(started_at)` | ✅ |
| `stopped_at` | `stopped_at` | not queried (duration_seconds used instead) | ✅ |
| `duration_seconds` | `duration_seconds` | `avg(duration_seconds)`, `argMax(duration_seconds, ...)` | ✅ |
| `collected_at` | — (DEFAULT now()) | not queried | ✅ |

### Datasource UID

| Surface | Value | Match |
|---------|-------|-------|
| `infra/grafana/provisioning/datasources/clickhouse.yaml` | `clickhouse-polytool` | — |
| Dashboard panel 1 `datasource.uid` | `clickhouse-polytool` | ✅ |
| Dashboard panel 2 `datasource.uid` | `clickhouse-polytool` | ✅ |
| Dashboard panel 3 `datasource.uid` | `clickhouse-polytool` | ✅ |
| Dashboard panel 4 `datasource.uid` | `clickhouse-polytool` | ✅ |
| Dashboard target 1 `datasource.type` | `grafana-clickhouse-datasource` | ✅ |

### Dashboard file path and provisioning

| Surface | Value | Match |
|---------|-------|-------|
| File on disk | `infra/grafana/dashboards/ris-pipeline-health.json` | — |
| docker-compose.yml volume mount | `./infra/grafana/dashboards:/var/lib/grafana/dashboards:ro` | ✅ |
| `dashboards.yaml` watched path | `/var/lib/grafana/dashboards` | ✅ |
| WP4-C dev log stated path | `infra/grafana/dashboards/ris-pipeline-health.json` | ✅ |

Dashboard is auto-provisioned on Grafana container start. No manual import needed.

### Workflow file name and canonical import registration

| Surface | Value | Match |
|---------|-------|-------|
| File on disk | `infra/n8n/workflows/ris-n8n-metrics-collector.json` | — |
| `CANONICAL_WORKFLOWS` entry | `("METRICS_COLLECTOR_ID", "ris-n8n-metrics-collector.json")` | ✅ |
| Workflow JSON `name` field | `"RIS -- n8n Execution Metrics Collector"` | ✅ |
| WP4-B dev log workflow name | `RIS -- n8n Execution Metrics Collector` | ✅ |

### Environment variable wiring (collector runtime)

| Requirement | docker-compose.yml n8n service | .env.example | Match |
|---|---|---|---|
| `CLICKHOUSE_PASSWORD` in n8n env | `- CLICKHOUSE_PASSWORD=${CLICKHOUSE_PASSWORD}` | pre-existing | ✅ |
| `N8N_API_KEY` in n8n env | `- N8N_API_KEY=${N8N_API_KEY:-}` | `N8N_API_KEY=replace_with_api_key_from_n8n_ui` | ✅ |
| Collector reads `$env.CLICKHOUSE_PASSWORD` | workflow JSON httpRequest header | — | ✅ |
| Collector reads `$env.N8N_API_KEY` | workflow JSON httpRequest header | — | ✅ |

### ClickHouse user routing

| Surface | User | Purpose | Consistent |
|---------|------|---------|------------|
| Collector `X-ClickHouse-User` header | `polytool_admin` | writes execution rows | ✅ |
| Grafana datasource `username` | `grafana_ro` | reads for dashboard panels | ✅ |
| DDL `GRANT SELECT ... TO` | `grafana_ro` | read access for Grafana | ✅ |

### Network routing (from within docker-compose)

| Leg | URL | Correctness |
|-----|-----|-------------|
| Collector → n8n API (self) | `http://localhost:5678/api/v1/executions` | ✅ localhost-to-self within n8n container |
| Collector → ClickHouse | `http://clickhouse:8123/` | ✅ compose service name; both on `polytool` network |

### ReplacingMergeTree / FINAL correctness

| Surface | Value | Match |
|---------|-------|-------|
| DDL engine | `ReplacingMergeTree(collected_at)` | — |
| Dashboard panel 1 rawSql | `FROM polytool.n8n_execution_metrics FINAL` | ✅ |
| Dashboard panel 2 rawSql | `FROM polytool.n8n_execution_metrics FINAL` | ✅ |
| Dashboard panel 3 rawSql | `FROM polytool.n8n_execution_metrics FINAL` | ✅ |
| Dashboard panel 4 rawSql | `FROM polytool.n8n_execution_metrics FINAL` + `argMax` pattern | ✅ |

### Workflow ships disabled

| Surface | Value | Correct |
|---------|-------|---------|
| `ris-n8n-metrics-collector.json` `active` field | `false` | ✅ (operator activates after env var verification) |

---

## Inconsistencies Found

**None.** All surfaces are internally consistent.

---

## Commands Run / Validation Results

```
python -m polytool --help
```
**Result:** CLI loads cleanly. No import errors.

Python inline cross-check (run manually):
```python
import json, pathlib
wf = json.loads(pathlib.Path('infra/n8n/workflows/ris-n8n-metrics-collector.json').read_text())
ds = json.loads(pathlib.Path('infra/grafana/dashboards/ris-pipeline-health.json').read_text())
```
- Collector workflow: 4 nodes, `active: false`, INSERT targets `polytool.n8n_execution_metrics`
- Dashboard: 4 panels, all on `clickhouse-polytool`, all query `polytool.n8n_execution_metrics FINAL`

---

## Phase 2A Monitoring Activation Readiness

| Component | Status |
|-----------|--------|
| WP4-A DDL (`28_n8n_execution_metrics.sql`) | Ready — applied on next `docker compose up` |
| WP4-B collector workflow (`ris-n8n-metrics-collector.json`) | Ready — ships with `active: false`, operator activates post-key-generation |
| WP4-B activation plumbing (compose env, import registry) | Ready — env vars wired, workflow in CANONICAL_WORKFLOWS |
| WP4-C Grafana dashboard (`ris-pipeline-health.json`) | Ready — auto-provisioned by Grafana at container start |

**Single remaining manual step:** Generate `N8N_API_KEY` from the n8n UI (Settings → API) after
first login, add to `.env`, restart the n8n container, and run
`python infra/n8n/import_workflows.py --no-activate` to register all three canonical
workflows. Then activate the metrics collector from the n8n UI.

**WP4-D (stale pipeline alert)** is the only outstanding RIS Phase 2A work packet.

---

**Codex review tier:** Skip (read-only verification log — no code changes).
