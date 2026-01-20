-- PolyTool Packet 3 Tables
-- Market metadata, daily features, and detector results

-- market_tokens: maps token_id to market/outcome metadata
-- Source: Gamma API /markets endpoint
-- Used for: joining trades to categories, outcome pairing detection
CREATE TABLE IF NOT EXISTS polyttool.market_tokens
(
    token_id String,
    condition_id String,
    outcome_index UInt8,
    outcome_name String,
    market_slug String,
    question String,
    category String DEFAULT '',
    event_slug String DEFAULT '',
    end_date_iso Nullable(DateTime),
    active UInt8 DEFAULT 1,
    raw_json String,
    ingested_at DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(ingested_at)
ORDER BY (token_id);

-- markets: full market metadata for reference
-- Stores complete market info including all outcomes
CREATE TABLE IF NOT EXISTS polyttool.markets
(
    condition_id String,
    market_slug String,
    question String,
    description String DEFAULT '',
    category String DEFAULT '',
    tags Array(String) DEFAULT [],
    event_slug String DEFAULT '',
    event_title String DEFAULT '',
    outcomes Array(String),
    clob_token_ids Array(String),
    start_date_iso Nullable(DateTime),
    end_date_iso Nullable(DateTime),
    close_date_iso Nullable(DateTime),
    active UInt8 DEFAULT 1,
    liquidity Float64 DEFAULT 0,
    volume Float64 DEFAULT 0,
    raw_json String,
    ingested_at DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(ingested_at)
ORDER BY (condition_id);

-- user_daily_features: aggregated trading metrics per user per day
-- Computed from user_trades with optional market_tokens join
CREATE TABLE IF NOT EXISTS polyttool.user_daily_features
(
    proxy_wallet String,
    bucket_day Date,
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
ORDER BY (proxy_wallet, bucket_day);

-- detector_results: strategy detection scores with evidence
-- Each detector produces a score (0-1), label, and evidence JSON
CREATE TABLE IF NOT EXISTS polyttool.detector_results
(
    proxy_wallet String,
    detector_name String,        -- HOLDING_STYLE, DCA_LADDERING, etc.
    bucket_type String,          -- 'day', 'all'
    bucket_start Date,
    score Float64,               -- 0.0 to 1.0
    label String,                -- e.g., 'SCALPER', 'SWING', 'HOLDER'
    evidence_json String,        -- JSON object with supporting metrics
    computed_at DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(computed_at)
ORDER BY (proxy_wallet, detector_name, bucket_type, bucket_start);

-- Grant SELECT access to grafana_ro user for all new tables
GRANT SELECT ON polyttool.market_tokens TO grafana_ro;
GRANT SELECT ON polyttool.markets TO grafana_ro;
GRANT SELECT ON polyttool.user_daily_features TO grafana_ro;
GRANT SELECT ON polyttool.detector_results TO grafana_ro;
