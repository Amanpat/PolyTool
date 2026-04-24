# WP4-A: n8n Execution Metrics — ClickHouse DDL

**Date:** 2026-04-23
**Work packet:** WP4-A (RIS Phase 2A monitoring infrastructure)
**Lane:** Infra-only; runs in parallel with n8n workflow lane (WP4-B/WP4-C not touched)

---

## What Changed and Why

**Created:** `infra/clickhouse/initdb/28_n8n_execution_metrics.sql`

WP4-A is the infra prerequisite for the RIS monitoring stack. The n8n execution
metrics collector (WP4-B) and Grafana RIS dashboard (WP4-C) both depend on this
table existing in ClickHouse before they are built. This DDL can be applied on
the next `docker compose up` or manually via the ClickHouse HTTP interface.

---

## Final Table Shape

| Column           | Type                       | Notes |
|------------------|----------------------------|-------|
| `execution_id`   | `String`                   | Dedup key (ORDER BY); sourced from n8n `/api/v1/executions` `id` field |
| `workflow_id`    | `String`                   | n8n `workflowId`; stable across execution retries |
| `workflow_name`  | `LowCardinality(String)`   | n8n `workflowName`; bounded vocabulary of ~5–10 RIS pipelines |
| `status`         | `LowCardinality(String)`   | `success \| error \| running \| waiting \| canceled \| crashed` |
| `mode`           | `LowCardinality(String)`   | `manual \| trigger \| webhook \| retry` |
| `started_at`     | `DateTime('UTC')`          | Primary time dimension; drives partition and TTL |
| `stopped_at`     | `Nullable(DateTime('UTC'))` | Null while `status = running` |
| `duration_seconds` | `Nullable(Float64)`      | Precomputed by WP4-B collector; null while running |
| `collected_at`   | `DateTime DEFAULT now()`   | Version column for ReplacingMergeTree; latest collection wins |

---

## Engine / Partition / TTL Choices

**Engine: `ReplacingMergeTree(collected_at)`**

The WP4-B hourly collector will re-fetch the same `execution_id` across runs
because an execution that was `running` at collection time may have transitioned
to `success` by the next pass. `ReplacingMergeTree(collected_at)` means ClickHouse
collapses duplicate `execution_id` rows at merge time, keeping the row with the
latest `collected_at`. The collector needs no dedup logic; Grafana queries should
use `FINAL` or `argMax`-based aggregations to read collapsed state.

**Partition: `PARTITION BY toYYYYMM(started_at)`**

Monthly partitioning aligns TTL expiry with calendar-month boundaries. With a
90-day window, at most 3 partitions are live at any time. Grafana time-filter
queries skip whole partitions outside the selected range.

**TTL: `started_at + INTERVAL 90 DAY`**

Execution metrics are operational telemetry only. No long-term retention is
needed. 90 days matches the research note recommendation and covers two full
rolling months of pipeline visibility with room to investigate recent anomalies.

---

## Conventions Followed

- Prefix `28_` (continues from `27_wallet_discovery.sql`)
- `polytool` database namespace (`CREATE TABLE IF NOT EXISTS polytool.*`)
- `GRANT SELECT ON ... TO grafana_ro` — present on all telemetry tables
- `LowCardinality(String)` for bounded vocabulary fields (status, mode, workflow_name)
- No `SETTINGS index_granularity` override — matches recent files (27, 25) that omit it

---

## Commands Run / Validation Results

```
python -m polytool --help
```
**Result:** CLI loads cleanly. No import errors. DDL file is static SQL; it has no
Python import path. CLI smoke test confirms the repo is healthy after file creation.

**SQL lint:** No SQL linter (sqlfluff or equivalent) is configured in this repo.
Validation was performed by manual inspection against:
- ClickHouse `ReplacingMergeTree` syntax (ORDER BY, PARTITION BY, TTL clause ordering)
- Field-type choices cross-checked against existing tables in `infra/clickhouse/initdb/`
- `GRANT SELECT ... TO grafana_ro` pattern present on all telemetry tables

No automated SQL parse route available; this is the first file in the initdb
directory to use TTL.

---

## What Remains for WP4-B through WP4-D

| Item | Work packet | What it builds |
|------|-------------|----------------|
| n8n metrics collector workflow | WP4-B | Hourly n8n schedule → GET `/api/v1/executions` → Code node transforms → POST to ClickHouse HTTP interface with `FORMAT JSONEachRow`. Writes `execution_id`, `workflow_id`, `workflow_name`, `status`, `mode`, `started_at`, `stopped_at`, `duration_seconds`. |
| Grafana RIS dashboard | WP4-C | `infra/grafana/dashboards/ris-pipeline-health.json`. Four panels: success rate (time series), avg duration (time series), failure frequency by workflow (bar chart), last run status (table with green/red value mappings). |
| Stale pipeline alert | WP4-D | Grafana alert rule: `max(started_at) WHERE status='success'` per `workflow_name`. Fires when age > 6 hours. Configure "No Data" state → Alerting. |

WP4-A is complete. WP4-B through WP4-D build on this table without modifying it.

---

**Codex review tier:** Skip (DDL file — matches repo Codex policy exclusion for infra config).
