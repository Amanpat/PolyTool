-- Phase 1 / Bulk Historical Import Foundation v0
-- 2-minute price history via polymarket-apis PyPI
-- Source: get_all_price_history_by_token_id() endpoint (public, no API key)

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
