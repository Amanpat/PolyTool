-- Phase 1 / Bulk Historical Import Foundation v0
-- Jon-Becker dataset: 72.1M trades from prediction-market-analysis (MIT license)
-- Source: s3.jbecker.dev/data.tar.zst
-- Fields: timestamp, price (1-99c), size, taker_side, resolution, category

CREATE TABLE IF NOT EXISTS polytool.jb_trades
(
    ts              DateTime64(3, 'UTC'),
    platform        LowCardinality(String),
    market_id       String,
    token_id        String,
    price           Float64,
    size            Float64,
    taker_side      LowCardinality(String),
    resolution      LowCardinality(String),
    category        LowCardinality(String),
    source_file     String,
    import_run_id   String,
    imported_at     DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(imported_at)
ORDER BY (platform, market_id, token_id, ts, taker_side)
SETTINGS index_granularity = 8192;

GRANT SELECT ON polytool.jb_trades TO grafana_ro;
