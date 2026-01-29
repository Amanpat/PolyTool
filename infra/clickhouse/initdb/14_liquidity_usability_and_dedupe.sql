-- Liquidity usability layer + deduped joins + opportunity storage

CREATE TABLE IF NOT EXISTS polyttool.user_opportunities_bucket
(
    proxy_wallet String,
    bucket_start DateTime,
    bucket_type String,
    token_id String,
    market_slug String,
    question String,
    outcome_name String,
    execution_cost_bps_100 Float64,
    depth_bid_usd_50bps Float64,
    depth_ask_usd_50bps Float64,
    liquidity_grade String,
    status String,
    computed_at DateTime DEFAULT now()
)
ENGINE = MergeTree
ORDER BY (proxy_wallet, bucket_start);

CREATE OR REPLACE VIEW polyttool.orderbook_snapshots_enriched AS
SELECT
    s.snapshot_ts AS snapshot_ts,
    s.token_id AS token_id,
    s.resolved_token_id AS resolved_token_id,
    coalesce(mt.market_slug, me.market_slug, '') AS market_slug,
    coalesce(mt.question, me.question, '') AS question,
    coalesce(mt.outcome_name, '') AS outcome_name,
    coalesce(mt.category, me.category, '') AS category,
    s.status AS status,
    s.reason AS reason,
    s.best_bid AS best_bid,
    s.best_ask AS best_ask,
    s.spread_bps AS spread_bps,
    s.depth_bid_usd_50bps AS depth_bid_usd_50bps,
    s.depth_ask_usd_50bps AS depth_ask_usd_50bps,
    s.slippage_buy_bps_100 AS slippage_buy_bps_100,
    s.slippage_sell_bps_100 AS slippage_sell_bps_100,
    s.usable_spread AS usable_spread,
    s.usable_depth AS usable_depth,
    s.usable_slippage_100 AS usable_slippage_100,
    s.usable_liquidity AS usable_liquidity,
    s.execution_cost_bps_100 AS execution_cost_bps_100,
    s.liquidity_grade AS liquidity_grade
FROM (
    SELECT
        s.snapshot_ts AS snapshot_ts,
        s.token_id AS token_id,
        coalesce(nullIf(ta.canonical_clob_token_id, ''), s.token_id) AS resolved_token_id,
        s.status AS status,
        s.reason AS reason,
        s.best_bid AS best_bid,
        s.best_ask AS best_ask,
        s.spread_bps AS spread_bps,
        s.depth_bid_usd_50bps AS depth_bid_usd_50bps,
        s.depth_ask_usd_50bps AS depth_ask_usd_50bps,
        s.slippage_buy_bps_100 AS slippage_buy_bps_100,
        s.slippage_sell_bps_100 AS slippage_sell_bps_100,
        if(isNull(s.spread_bps), 0, s.spread_bps <= 200) AS usable_spread,
        if(
            isNull(s.depth_bid_usd_50bps) OR isNull(s.depth_ask_usd_50bps),
            0,
            s.depth_bid_usd_50bps >= 500 AND s.depth_ask_usd_50bps >= 500
        ) AS usable_depth,
        if(
            isNull(s.slippage_buy_bps_100) OR isNull(s.slippage_sell_bps_100),
            0,
            s.slippage_buy_bps_100 <= 100 AND s.slippage_sell_bps_100 <= 100
        ) AS usable_slippage_100,
        if(
            s.status = 'ok'
            AND if(isNull(s.spread_bps), 0, s.spread_bps <= 200)
            AND if(
                isNull(s.depth_bid_usd_50bps) OR isNull(s.depth_ask_usd_50bps),
                0,
                s.depth_bid_usd_50bps >= 500 AND s.depth_ask_usd_50bps >= 500
            )
            AND if(
                isNull(s.slippage_buy_bps_100) OR isNull(s.slippage_sell_bps_100),
                0,
                s.slippage_buy_bps_100 <= 100 AND s.slippage_sell_bps_100 <= 100
            ),
            1,
            0
        ) AS usable_liquidity,
        greatest(
            ifNull(s.spread_bps, 0),
            ifNull(s.slippage_buy_bps_100, 0),
            ifNull(s.slippage_sell_bps_100, 0)
        ) AS execution_cost_bps_100,
        multiIf(
            s.status = 'ok'
            AND if(isNull(s.spread_bps), 0, s.spread_bps <= 200)
            AND if(
                isNull(s.depth_bid_usd_50bps) OR isNull(s.depth_ask_usd_50bps),
                0,
                s.depth_bid_usd_50bps >= 500 AND s.depth_ask_usd_50bps >= 500
            )
            AND if(
                isNull(s.slippage_buy_bps_100) OR isNull(s.slippage_sell_bps_100),
                0,
                s.slippage_buy_bps_100 <= 100 AND s.slippage_sell_bps_100 <= 100
            ),
            'HIGH',
            s.status = 'ok'
            AND ifNull(s.spread_bps, 1e9) <= 500
            AND ifNull(s.depth_bid_usd_50bps, 0) >= 200
            AND ifNull(s.depth_ask_usd_50bps, 0) >= 200,
            'MED',
            'LOW'
        ) AS liquidity_grade
    FROM polyttool.token_orderbook_snapshots s
    LEFT JOIN polyttool.token_aliases ta ON s.token_id = ta.alias_token_id
) s
LEFT JOIN (
    SELECT
        token_id,
        argMax(market_slug, ingested_at) AS market_slug,
        argMax(question, ingested_at) AS question,
        argMax(outcome_name, ingested_at) AS outcome_name,
        argMax(category, ingested_at) AS category,
        argMax(condition_id, ingested_at) AS condition_id,
        max(ifNull(enable_order_book, 0)) AS enable_order_book,
        max(ifNull(accepting_orders, 0)) AS accepting_orders
    FROM polyttool.market_tokens
    GROUP BY token_id
) mt ON mt.token_id = s.resolved_token_id
LEFT JOIN (
    SELECT
        condition_id,
        argMax(market_slug, ingested_at) AS market_slug,
        argMax(question, ingested_at) AS question,
        argMax(category, ingested_at) AS category
    FROM polyttool.markets
    GROUP BY condition_id
) me ON if(
    startsWith(lowerUTF8(trimBoth(mt.condition_id)), '0x'),
    concat('0x', substring(lowerUTF8(trimBoth(mt.condition_id)), 3)),
    concat('0x', lowerUTF8(trimBoth(mt.condition_id)))
) = if(
    startsWith(lowerUTF8(trimBoth(me.condition_id)), '0x'),
    concat('0x', substring(lowerUTF8(trimBoth(me.condition_id)), 3)),
    concat('0x', lowerUTF8(trimBoth(me.condition_id)))
);

GRANT SELECT ON polyttool.user_opportunities_bucket TO grafana_ro;
GRANT SELECT ON polyttool.orderbook_snapshots_enriched TO grafana_ro;
