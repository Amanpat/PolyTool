-- RIS Phase 2A — WP4-A: n8n execution metrics sink
-- ROADMAP: docs/obsidian-vault/Claude Desktop/09-Decisions/RIS_OPERATIONAL_READINESS_ROADMAP_v1.1.md § WP4-A
-- Downstream: WP4-B (hourly collector workflow), WP4-C (Grafana RIS pipeline-health dashboard)
--
-- DESIGN NOTES:
-- Engine: ReplacingMergeTree(collected_at)
--   The WP4-B hourly collector may re-fetch the same execution_id as its status
--   transitions (e.g. running → success). The later collected_at wins, so queries
--   always see the most up-to-date status without dedup logic in the collector.
--   Use FINAL qualifier or dedup-aware aggregations (argMax) in Grafana queries.
-- Partition: toYYYYMM(started_at)
--   Aligns TTL expiry with calendar-month boundaries; reduces scan cost for
--   time-filtered Grafana queries across the 90-day retention window.
-- TTL: 90 days from started_at
--   Execution metrics are operational telemetry only; no long-term retention needed.
-- Fields sourced from: GET /api/v1/executions on the n8n REST API (id, workflowId,
--   workflowName, status, mode, startedAt, stoppedAt). duration_seconds is
--   precomputed by the collector as (stoppedAt - startedAt) in seconds.

-- ---------------------------------------------------------------------------
-- Table: polytool.n8n_execution_metrics
-- One row per n8n execution attempt, idempotent on execution_id.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS polytool.n8n_execution_metrics
(
    execution_id      String,
    workflow_id       String,
    workflow_name     LowCardinality(String),
    status            LowCardinality(String),    -- success | error | running | waiting | canceled | crashed
    mode              LowCardinality(String),    -- manual | trigger | webhook | retry
    started_at        DateTime('UTC'),
    stopped_at        Nullable(DateTime('UTC')),
    duration_seconds  Nullable(Float64),         -- (stopped_at - started_at); null while status = running
    collected_at      DateTime                   DEFAULT now()
)
ENGINE = ReplacingMergeTree(collected_at)
PARTITION BY toYYYYMM(started_at)
ORDER BY execution_id
TTL started_at + INTERVAL 90 DAY;

GRANT SELECT ON polytool.n8n_execution_metrics TO grafana_ro;
