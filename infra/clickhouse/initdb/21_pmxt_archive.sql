-- Phase 1 / Bulk Historical Import Foundation v0
-- pmxt archive: hourly L2 orderbook snapshots from archive.pmxt.dev
-- Source: Parquet files under Polymarket/ Kalshi/ Opinion/
-- Import: python -m polytool import-historical validate-layout --source-kind pmxt_archive

CREATE TABLE IF NOT EXISTS polytool.pmxt_l2_snapshots
(
    snapshot_ts     DateTime64(3, 'UTC'),
    platform        LowCardinality(String),
    market_id       String,
    token_id        String,
    side            LowCardinality(String),
    price           Float64,
    size            Float64,
    source_file     String,
    import_run_id   String,
    imported_at     DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(imported_at)
ORDER BY (platform, market_id, token_id, side, price, snapshot_ts)
SETTINGS index_granularity = 8192;

GRANT SELECT ON polytool.pmxt_l2_snapshots TO grafana_ro;
