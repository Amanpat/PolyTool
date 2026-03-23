-- Phase 1 / Bulk Historical Import Foundation v0
-- 2-minute price history bulk import from local files (legacy path, off critical path under v4.2)
-- Source: get_all_price_history_by_token_id() endpoint (public, no API key)
--
-- NAMING NOTE (v4.2):
-- price_history_2min (this table) = legacy one-time bulk import from local JSONL/CSV files
--                                   Written by: python -m polytool import-historical --source-kind price_history_2min
--                                   Status: off critical path under v4.2; retained as optional cache
-- price_2min (table 24)           = live-updating ClickHouse series
--                                   Written by: python -m polytool fetch-price-2min
--                                   Status: canonical series for Silver reconstruction (v4.2)
-- See docs/dev_logs/2026-03-16_price_2min_clickhouse_v0.md for the naming decision.

CREATE TABLE IF NOT EXISTS polytool.price_history_2min
(
    token_id        String,
    ts              DateTime64(3, 'UTC'),
    price           Float64,
    source          LowCardinality(String) DEFAULT 'polymarket_apis',
    import_run_id   String,
    imported_at     DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(imported_at)
ORDER BY (token_id, ts)
SETTINGS index_granularity = 8192;

GRANT SELECT ON polytool.price_history_2min TO grafana_ro;
