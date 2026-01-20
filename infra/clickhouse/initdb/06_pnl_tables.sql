-- PolyTool Packet 5.1 Tables
-- PnL and exposure by bucket

CREATE TABLE IF NOT EXISTS polyttool.user_pnl_bucket
(
    proxy_wallet String,
    bucket_type String,               -- 'day', 'hour', 'week'
    bucket_start DateTime,
    realized_pnl Float64,
    mtm_pnl_estimate Float64,
    exposure_notional_estimate Float64,
    open_position_tokens Int64,
    pricing_source String,
    computed_at DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(computed_at)
ORDER BY (proxy_wallet, bucket_type, bucket_start);

GRANT SELECT ON polyttool.user_pnl_bucket TO grafana_ro;
