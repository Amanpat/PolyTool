-- PolyTool Packet 3.1 Tables
-- Bucket-granular features (day/hour/week)

-- user_bucket_features: aggregated trading metrics per user per time bucket
-- Supports day, hour, and week granularity
CREATE TABLE IF NOT EXISTS polyttool.user_bucket_features
(
    proxy_wallet String,
    bucket_type String,          -- 'day', 'hour', 'week'
    bucket_start DateTime,       -- Start of the bucket period
    trades_count UInt32,
    buys_count UInt32,
    sells_count UInt32,
    volume Float64,              -- sum(size)
    notional Float64,            -- sum(size * price)
    unique_tokens UInt32,
    unique_markets UInt32,       -- requires market_tokens join
    avg_trade_size Float64,
    pct_buys Float64,
    pct_sells Float64,
    mapping_coverage Float64,    -- % of trades with token_id in market_tokens
    computed_at DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(computed_at)
ORDER BY (proxy_wallet, bucket_type, bucket_start);

-- Grant SELECT access to grafana_ro user
GRANT SELECT ON polyttool.user_bucket_features TO grafana_ro;
