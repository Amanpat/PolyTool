-- Token alias mapping and resolved views

-- token_aliases: map Data API token_ids (or other aliases) to canonical CLOB token ids
CREATE TABLE IF NOT EXISTS polyttool.token_aliases
(
    alias_token_id String,
    canonical_clob_token_id String,
    condition_id String DEFAULT '',
    outcome_index UInt8 DEFAULT 0,
    outcome_name String DEFAULT '',
    market_slug String DEFAULT '',
    raw_json String,
    ingested_at DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(ingested_at)
ORDER BY (alias_token_id, canonical_clob_token_id);

GRANT SELECT ON polyttool.token_aliases TO grafana_ro;

-- Resolve user_trades tokens to canonical CLOB token ids
CREATE OR REPLACE VIEW polyttool.user_trades_resolved AS
WITH
    lowerUTF8(trimBoth(t.condition_id)) AS condition_lower,
    if(
        condition_lower = '',
        '',
        if(startsWith(condition_lower, '0x'),
            concat('0x', substring(condition_lower, 3)),
            concat('0x', condition_lower)
        )
    ) AS condition_id_norm,
    lowerUTF8(trimBoth(t.outcome)) AS outcome_norm,
    arrayMap(x -> lowerUTF8(x), ifNull(m.outcomes, [])) AS outcomes_norm,
    indexOf(outcomes_norm, outcome_norm) AS outcome_pos
SELECT
    t.proxy_wallet,
    t.trade_uid,
    t.ts,
    t.token_id,
    t.condition_id,
    t.outcome,
    t.side,
    t.size,
    t.price,
    t.transaction_hash,
    t.raw_json,
    t.ingested_at,
    condition_id_norm AS normalized_condition_id,
    coalesce(
        mt_direct.token_id,
        nullIf(ta.canonical_clob_token_id, ''),
        if(outcome_pos > 0, arrayElement(ifNull(m.clob_token_ids, []), outcome_pos), NULL),
        t.token_id
    ) AS resolved_token_id,
    coalesce(
        mt_direct.condition_id,
        mt_alias.condition_id,
        nullIf(ta.condition_id, ''),
        condition_id_norm
    ) AS resolved_condition_id,
    coalesce(
        mt_direct.outcome_index,
        mt_alias.outcome_index,
        ta.outcome_index,
        if(outcome_pos > 0, toUInt8(outcome_pos - 1), NULL)
    ) AS resolved_outcome_index,
    coalesce(
        mt_direct.outcome_name,
        mt_alias.outcome_name,
        nullIf(ta.outcome_name, ''),
        if(outcome_pos > 0, arrayElement(ifNull(m.outcomes, []), outcome_pos), NULL),
        t.outcome
    ) AS resolved_outcome_name,
    coalesce(mt_direct.market_slug, mt_alias.market_slug, nullIf(ta.market_slug, ''), m.market_slug, '') AS market_slug,
    coalesce(mt_direct.question, mt_alias.question, m.question, '') AS question,
    coalesce(mt_direct.category, mt_alias.category, m.category, '') AS category,
    coalesce(mt_direct.event_slug, mt_alias.event_slug, m.event_slug, '') AS event_slug,
    coalesce(mt_direct.end_date_iso, mt_alias.end_date_iso, m.end_date_iso) AS end_date_iso,
    coalesce(mt_direct.active, mt_alias.active, m.active, 0) AS active,
    multiIf(
        mt_direct.token_id IS NOT NULL, 'direct',
        length(ta.canonical_clob_token_id) > 0, 'alias',
        outcome_pos > 0, 'condition_outcome',
        'unresolved'
    ) AS resolution_source
FROM polyttool.user_trades AS t
LEFT JOIN polyttool.market_tokens AS mt_direct ON t.token_id = mt_direct.token_id
LEFT JOIN polyttool.token_aliases AS ta ON t.token_id = ta.alias_token_id
LEFT JOIN polyttool.market_tokens AS mt_alias ON ta.canonical_clob_token_id = mt_alias.token_id
LEFT JOIN polyttool.markets AS m ON if(
    startsWith(lowerUTF8(trimBoth(m.condition_id)), '0x'),
    concat('0x', substring(lowerUTF8(trimBoth(m.condition_id)), 3)),
    concat('0x', lowerUTF8(trimBoth(m.condition_id)))
) = condition_id_norm;

GRANT SELECT ON polyttool.user_trades_resolved TO grafana_ro;

-- Resolve user_positions snapshots to canonical CLOB token ids
CREATE OR REPLACE VIEW polyttool.user_positions_resolved AS
WITH
    lowerUTF8(trimBoth(p.condition_id)) AS condition_lower,
    if(
        condition_lower = '',
        '',
        if(startsWith(condition_lower, '0x'),
            concat('0x', substring(condition_lower, 3)),
            concat('0x', condition_lower)
        )
    ) AS condition_id_norm,
    lowerUTF8(trimBoth(p.outcome)) AS outcome_norm,
    arrayMap(x -> lowerUTF8(x), ifNull(m.outcomes, [])) AS outcomes_norm,
    indexOf(outcomes_norm, outcome_norm) AS outcome_pos
SELECT
    p.proxy_wallet,
    p.snapshot_ts,
    p.token_id,
    p.condition_id,
    p.outcome,
    p.shares,
    p.avg_cost,
    p.raw_json,
    p.ingested_at,
    condition_id_norm AS normalized_condition_id,
    coalesce(
        mt_direct.token_id,
        nullIf(ta.canonical_clob_token_id, ''),
        if(outcome_pos > 0, arrayElement(ifNull(m.clob_token_ids, []), outcome_pos), NULL),
        p.token_id
    ) AS resolved_token_id,
    coalesce(
        mt_direct.condition_id,
        mt_alias.condition_id,
        nullIf(ta.condition_id, ''),
        condition_id_norm
    ) AS resolved_condition_id,
    coalesce(
        mt_direct.outcome_index,
        mt_alias.outcome_index,
        ta.outcome_index,
        if(outcome_pos > 0, toUInt8(outcome_pos - 1), NULL)
    ) AS resolved_outcome_index,
    coalesce(
        mt_direct.outcome_name,
        mt_alias.outcome_name,
        nullIf(ta.outcome_name, ''),
        if(outcome_pos > 0, arrayElement(ifNull(m.outcomes, []), outcome_pos), NULL),
        p.outcome
    ) AS resolved_outcome_name,
    coalesce(mt_direct.market_slug, mt_alias.market_slug, nullIf(ta.market_slug, ''), m.market_slug, '') AS market_slug,
    coalesce(mt_direct.question, mt_alias.question, m.question, '') AS question,
    coalesce(mt_direct.category, mt_alias.category, m.category, '') AS category,
    coalesce(mt_direct.event_slug, mt_alias.event_slug, m.event_slug, '') AS event_slug,
    coalesce(mt_direct.end_date_iso, mt_alias.end_date_iso, m.end_date_iso) AS end_date_iso,
    coalesce(mt_direct.active, mt_alias.active, m.active, 0) AS active,
    multiIf(
        mt_direct.token_id IS NOT NULL, 'direct',
        length(ta.canonical_clob_token_id) > 0, 'alias',
        outcome_pos > 0, 'condition_outcome',
        'unresolved'
    ) AS resolution_source
FROM polyttool.user_positions_snapshots AS p
LEFT JOIN polyttool.market_tokens AS mt_direct ON p.token_id = mt_direct.token_id
LEFT JOIN polyttool.token_aliases AS ta ON p.token_id = ta.alias_token_id
LEFT JOIN polyttool.market_tokens AS mt_alias ON ta.canonical_clob_token_id = mt_alias.token_id
LEFT JOIN polyttool.markets AS m ON if(
    startsWith(lowerUTF8(trimBoth(m.condition_id)), '0x'),
    concat('0x', substring(lowerUTF8(trimBoth(m.condition_id)), 3)),
    concat('0x', lowerUTF8(trimBoth(m.condition_id)))
) = condition_id_norm;

GRANT SELECT ON polyttool.user_positions_resolved TO grafana_ro;

-- Resolve user activity tokens to canonical CLOB token ids
CREATE OR REPLACE VIEW polyttool.user_activity_resolved AS
WITH
    lowerUTF8(trimBoth(a.condition_id)) AS condition_lower,
    if(
        condition_lower = '',
        '',
        if(startsWith(condition_lower, '0x'),
            concat('0x', substring(condition_lower, 3)),
            concat('0x', condition_lower)
        )
    ) AS condition_id_norm
SELECT
    a.proxy_wallet,
    a.activity_uid,
    a.ts,
    a.activity_type,
    a.token_id,
    a.condition_id,
    a.size,
    a.price,
    a.tx_hash,
    a.raw_json,
    a.ingested_at,
    condition_id_norm AS normalized_condition_id,
    coalesce(mt_direct.token_id, nullIf(ta.canonical_clob_token_id, ''), a.token_id) AS resolved_token_id,
    coalesce(mt_direct.condition_id, mt_alias.condition_id, nullIf(ta.condition_id, ''), condition_id_norm) AS resolved_condition_id,
    coalesce(mt_direct.outcome_name, mt_alias.outcome_name, nullIf(ta.outcome_name, ''), '') AS resolved_outcome_name,
    coalesce(mt_direct.market_slug, mt_alias.market_slug, nullIf(ta.market_slug, ''), m.market_slug, '') AS market_slug,
    coalesce(mt_direct.question, mt_alias.question, m.question, '') AS question,
    coalesce(mt_direct.category, mt_alias.category, m.category, '') AS category,
    coalesce(mt_direct.event_slug, mt_alias.event_slug, m.event_slug, '') AS event_slug,
    coalesce(mt_direct.end_date_iso, mt_alias.end_date_iso, m.end_date_iso) AS end_date_iso,
    coalesce(mt_direct.active, mt_alias.active, m.active, 0) AS active,
    multiIf(
        mt_direct.token_id IS NOT NULL, 'direct',
        length(ta.canonical_clob_token_id) > 0, 'alias',
        'unresolved'
    ) AS resolution_source
FROM polyttool.user_activity AS a
LEFT JOIN polyttool.market_tokens AS mt_direct ON a.token_id = mt_direct.token_id
LEFT JOIN polyttool.token_aliases AS ta ON a.token_id = ta.alias_token_id
LEFT JOIN polyttool.market_tokens AS mt_alias ON ta.canonical_clob_token_id = mt_alias.token_id
LEFT JOIN polyttool.markets AS m ON if(
    startsWith(lowerUTF8(trimBoth(m.condition_id)), '0x'),
    concat('0x', substring(lowerUTF8(trimBoth(m.condition_id)), 3)),
    concat('0x', lowerUTF8(trimBoth(m.condition_id)))
) = condition_id_norm;

GRANT SELECT ON polyttool.user_activity_resolved TO grafana_ro;

-- Enrich orderbook snapshots using canonical token ids
CREATE OR REPLACE VIEW polyttool.orderbook_snapshots_enriched AS
SELECT
    s.snapshot_ts AS snapshot_ts,
    s.token_id AS token_id,
    coalesce(ta.canonical_clob_token_id, s.token_id) AS resolved_token_id,
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
LEFT JOIN polyttool.token_aliases ta ON s.token_id = ta.alias_token_id
LEFT JOIN polyttool.market_tokens mt ON mt.token_id = coalesce(ta.canonical_clob_token_id, s.token_id);

GRANT SELECT ON polyttool.orderbook_snapshots_enriched TO grafana_ro;
