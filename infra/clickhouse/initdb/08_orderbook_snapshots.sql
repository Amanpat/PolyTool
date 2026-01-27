-- Orderbook snapshots for liquidity tracking

CREATE TABLE IF NOT EXISTS polyttool.token_orderbook_snapshots
(
    token_id String,
    snapshot_ts DateTime,
    best_bid Nullable(Float64),
    best_ask Nullable(Float64),
    mid_price Nullable(Float64),
    spread_bps Nullable(Float64),
    depth_bid_usd_50bps Nullable(Float64),
    depth_ask_usd_50bps Nullable(Float64),
    slippage_buy_bps_100 Nullable(Float64),
    slippage_sell_bps_100 Nullable(Float64),
    slippage_buy_bps_500 Nullable(Float64),
    slippage_sell_bps_500 Nullable(Float64),
    levels_captured UInt32,
    book_timestamp Nullable(String),
    status String,
    reason Nullable(String),
    source String DEFAULT 'api_snapshot',
    ingested_at DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(ingested_at)
ORDER BY (token_id, snapshot_ts);

GRANT SELECT ON polyttool.token_orderbook_snapshots TO grafana_ro;

CREATE OR REPLACE VIEW polyttool.orderbook_snapshots_enriched AS
SELECT
    s.snapshot_ts AS snapshot_ts,
    s.token_id AS token_id,
    mt.market_slug AS market_slug,
    mt.question AS question,
    s.status AS status,
    s.reason AS reason,
    s.best_bid AS best_bid,
    s.best_ask AS best_ask,
    s.spread_bps AS spread_bps,
    s.depth_bid_usd_50bps AS depth_bid_usd_50bps,
    s.depth_ask_usd_50bps AS depth_ask_usd_50bps,
    s.slippage_buy_bps_100 AS slippage_buy_bps_100,
    s.slippage_sell_bps_100 AS slippage_sell_bps_100
FROM polyttool.token_orderbook_snapshots s
LEFT JOIN polyttool.market_tokens mt ON s.token_id = mt.token_id;

GRANT SELECT ON polyttool.orderbook_snapshots_enriched TO grafana_ro;
