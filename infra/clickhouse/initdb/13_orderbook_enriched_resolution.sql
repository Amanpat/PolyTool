-- Orderbook snapshots enrichment using token aliases + markets metadata

CREATE OR REPLACE VIEW polyttool.orderbook_snapshots_enriched AS
SELECT
    s.snapshot_ts AS snapshot_ts,
    s.token_id AS token_id,
    coalesce(nullIf(ta.canonical_clob_token_id, ''), s.token_id) AS resolved_token_id,
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
    s.slippage_sell_bps_100 AS slippage_sell_bps_100
FROM polyttool.token_orderbook_snapshots s
LEFT JOIN polyttool.token_aliases ta ON s.token_id = ta.alias_token_id
LEFT JOIN polyttool.market_tokens mt ON mt.token_id = coalesce(nullIf(ta.canonical_clob_token_id, ''), s.token_id)
LEFT JOIN polyttool.markets_enriched me ON if(
    startsWith(lowerUTF8(trimBoth(mt.condition_id)), '0x'),
    concat('0x', substring(lowerUTF8(trimBoth(mt.condition_id)), 3)),
    concat('0x', lowerUTF8(trimBoth(mt.condition_id)))
) = if(
    startsWith(lowerUTF8(trimBoth(me.condition_id)), '0x'),
    concat('0x', substring(lowerUTF8(trimBoth(me.condition_id)), 3)),
    concat('0x', lowerUTF8(trimBoth(me.condition_id)))
);

GRANT SELECT ON polyttool.orderbook_snapshots_enriched TO grafana_ro;
