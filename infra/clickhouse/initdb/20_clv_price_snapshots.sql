-- Roadmap 5.1A: CLV closing-price snapshots (cache-first, reproducible)

CREATE TABLE IF NOT EXISTS polyttool.market_price_snapshots
(
    token_id String,
    ts_observed DateTime64(3, 'UTC'),
    price Nullable(Float64),
    kind LowCardinality(String) DEFAULT 'closing',
    close_ts DateTime64(3, 'UTC'),
    source LowCardinality(String) DEFAULT 'clob_prices_history',
    query_window_seconds UInt32 DEFAULT 86400,
    interval LowCardinality(String) DEFAULT '1m',
    fidelity LowCardinality(String) DEFAULT 'high',
    fetched_at DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(fetched_at)
ORDER BY (token_id, kind, close_ts, ts_observed, query_window_seconds, interval, fidelity)
SETTINGS index_granularity = 8192;

GRANT SELECT ON polyttool.market_price_snapshots TO grafana_ro;
