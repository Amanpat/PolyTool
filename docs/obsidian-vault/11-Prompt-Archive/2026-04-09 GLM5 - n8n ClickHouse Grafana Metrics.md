---
tags: [prompt-archive]
date: 2026-04-09
model: GLM-5 Turbo
topic: n8n Execution Metrics to ClickHouse and Grafana
---
# n8n Execution Metrics → ClickHouse + Grafana — Research Results

## Key Findings
1. **n8n API fields:** `/api/v1/executions` returns id, workflowId, workflowName, status (success/error/running/waiting/canceled/crashed), mode, startedAt, stoppedAt, nextCursor for pagination.
2. **ClickHouse DDL:** `n8n_execution_metrics` table with MergeTree, partition by month, TTL 90 days. LowCardinality for workflow_name and status. ReplacingMergeTree with execution_id for idempotency.
3. **n8n workflow:** Schedule hourly → GET /api/v1/executions → Code node transforms → POST to ClickHouse HTTP interface with FORMAT JSONEachRow.
4. **Grafana panels:** Success rate (time series, countIf/count), avg duration (time series), failure frequency (bar chart by workflow), last run status (table with green/red value mappings via row_number() OVER PARTITION BY).
5. **Alerts:** Query max(started_at) WHERE status='success' per workflow. Alert when age > X hours. Configure "No Data" state to Alerting.

## Artifacts
- Complete n8n workflow JSON provided
- Complete Grafana dashboard JSON provided (3 panels, ClickHouse datasource)

## Applied To
- RIS Phase 2 Priority 2 (monitoring)
- `infra/clickhouse/initdb/` DDL migration
- `infra/grafana/dashboards/` dashboard JSON

## Source
Deep research prompt, discussed in [[10-Session-Notes/2026-04-09 RIS n8n Workflows and Phase 2 Roadmap]]
