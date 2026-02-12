-- Market resolution data for outcome determination
-- Maps (condition_id, outcome_token_id) to settlement outcome

-- Resolutions table: stores settlement price and resolution metadata
CREATE TABLE IF NOT EXISTS market_resolutions (
    condition_id String,
    outcome_token_id String,
    market_slug String,
    outcome_name String,
    -- Settlement price: 1.0 for winning outcome, 0.0 for losing outcome
    -- For binary markets: exactly one outcome has settlement_price=1.0
    -- For multi-outcome: one winner with 1.0, all others 0.0
    settlement_price Nullable(Float64),
    -- Resolution timestamp (when market was resolved)
    resolved_at DateTime64(3) NULL,
    -- Source of resolution data
    resolution_source LowCardinality(String) DEFAULT 'unknown',
    -- When we fetched this resolution
    fetched_at DateTime64(3) DEFAULT now64(3),
    -- Raw response for debugging
    raw_json String DEFAULT ''
) ENGINE = ReplacingMergeTree(fetched_at)
ORDER BY (condition_id, outcome_token_id)
SETTINGS index_granularity = 8192;

-- Index for faster lookups by outcome_token_id
CREATE INDEX IF NOT EXISTS idx_resolutions_token_id ON market_resolutions (outcome_token_id) TYPE bloom_filter GRANULARITY 1;

-- Index for faster lookups by market_slug
CREATE INDEX IF NOT EXISTS idx_resolutions_market_slug ON market_resolutions (market_slug) TYPE bloom_filter GRANULARITY 1;

-- View that enriches trades with resolution data
CREATE OR REPLACE VIEW user_trades_with_resolution AS
SELECT
    t.*,
    COALESCE(r.settlement_price, -1) AS settlement_price,
    r.resolved_at AS resolved_at,
    r.resolution_source AS resolution_source,
    -- Resolution outcome enum
    CASE
        WHEN r.settlement_price IS NULL THEN 'PENDING'
        WHEN r.settlement_price = 1.0 AND lowerUTF8(t.side) = 'buy' THEN 'WIN'
        WHEN r.settlement_price = 0.0 AND lowerUTF8(t.side) = 'buy' THEN 'LOSS'
        WHEN r.settlement_price = 1.0 AND lowerUTF8(t.side) = 'sell' THEN 'PROFIT_EXIT'
        WHEN r.settlement_price = 0.0 AND lowerUTF8(t.side) = 'sell' THEN 'LOSS_EXIT'
        ELSE 'UNKNOWN_RESOLUTION'
    END AS resolution_outcome
FROM user_trades_resolved t
LEFT JOIN market_resolutions r
    ON t.resolved_token_id = r.outcome_token_id
    OR t.token_id = r.outcome_token_id;

-- Trade lifecycle view with realized PnL calculation
CREATE OR REPLACE VIEW user_trade_lifecycle AS
SELECT
    proxy_wallet,
    resolved_token_id,
    market_slug,
    question,
    resolved_outcome_name AS outcome_name,
    -- Entry metrics (first buy)
    minIf(ts, lowerUTF8(side) = 'buy') AS entry_ts,
    avgIf(price, lowerUTF8(side) = 'buy') AS entry_price_avg,
    sumIf(size, lowerUTF8(side) = 'buy') AS total_bought,
    sumIf(size * price, lowerUTF8(side) = 'buy') AS total_cost,
    -- Exit metrics (first sell or resolution)
    minIf(ts, lowerUTF8(side) = 'sell') AS exit_ts,
    avgIf(price, lowerUTF8(side) = 'sell') AS exit_price_avg,
    sumIf(size, lowerUTF8(side) = 'sell') AS total_sold,
    sumIf(size * price, lowerUTF8(side) = 'sell') AS total_proceeds,
    -- Hold duration (entry to first exit or now)
    dateDiff(
        'second',
        minIf(ts, lowerUTF8(side) = 'buy'),
        COALESCE(minIf(ts, lowerUTF8(side) = 'sell'), now())
    ) AS hold_duration_seconds,
    -- Position remaining
    sumIf(size, lowerUTF8(side) = 'buy') - sumIf(size, lowerUTF8(side) = 'sell') AS position_remaining,
    -- Trade count
    count() AS trade_count,
    countIf(lowerUTF8(side) = 'buy') AS buy_count,
    countIf(lowerUTF8(side) = 'sell') AS sell_count
FROM user_trades_resolved
WHERE resolved_token_id != ''
GROUP BY
    proxy_wallet,
    resolved_token_id,
    market_slug,
    question,
    resolved_outcome_name;

-- Enriched lifecycle view with resolution and PnL
CREATE OR REPLACE VIEW user_trade_lifecycle_enriched AS
SELECT
    l.*,
    r.settlement_price,
    r.resolved_at,
    r.resolution_source,
    -- Resolution outcome
    CASE
        WHEN r.settlement_price IS NULL THEN 'PENDING'
        WHEN l.position_remaining > 0 AND r.settlement_price = 1.0 THEN 'WIN'
        WHEN l.position_remaining > 0 AND r.settlement_price = 0.0 THEN 'LOSS'
        WHEN l.position_remaining <= 0 AND l.total_proceeds > l.total_cost THEN 'PROFIT_EXIT'
        WHEN l.position_remaining <= 0 AND l.total_proceeds <= l.total_cost THEN 'LOSS_EXIT'
        ELSE 'UNKNOWN_RESOLUTION'
    END AS resolution_outcome,
    -- Gross PnL calculation
    CASE
        WHEN r.settlement_price IS NULL THEN 0  -- Pending
        WHEN l.position_remaining > 0 THEN
            -- Still holding: (settlement_price * remaining) + proceeds - cost
            (r.settlement_price * l.position_remaining) + l.total_proceeds - l.total_cost
        ELSE
            -- Fully exited: proceeds - cost
            l.total_proceeds - l.total_cost
    END AS gross_pnl,
    -- Fees placeholder (to be enriched by fee lookup)
    0.0 AS fees_estimated,
    0.0 AS fees_actual,
    'unknown' AS fees_source,
    -- Net PnL (gross - fees)
    CASE
        WHEN r.settlement_price IS NULL THEN 0
        WHEN l.position_remaining > 0 THEN
            (r.settlement_price * l.position_remaining) + l.total_proceeds - l.total_cost
        ELSE
            l.total_proceeds - l.total_cost
    END AS realized_pnl_net
FROM user_trade_lifecycle l
LEFT JOIN market_resolutions r
    ON l.resolved_token_id = r.outcome_token_id;
