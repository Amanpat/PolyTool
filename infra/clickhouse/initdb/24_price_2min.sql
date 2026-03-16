-- Phase 1 / price_2min acquisition path
-- Canonical live-updating 2-minute price series (v4.2 architecture)
--
-- NAMING NOTE:
-- price_2min  = this table: live-updating ClickHouse series, written by fetch-price-2min CLI
-- price_history_2min (table 23) = legacy one-time bulk import from local files (off critical path)
-- These are two different use cases for the same underlying API.
-- See docs/dev_logs/2026-03-16_price_2min_clickhouse_v0.md for the naming decision.

CREATE TABLE IF NOT EXISTS polytool.price_2min
(
    token_id        String,
    ts              DateTime64(3, 'UTC'),
    price           Float64,
    source          LowCardinality(String) DEFAULT 'clob_api',
    import_run_id   String,
    imported_at     DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(imported_at)
ORDER BY (token_id, ts)
SETTINGS index_granularity = 8192;

GRANT SELECT ON polytool.price_2min TO grafana_ro;
