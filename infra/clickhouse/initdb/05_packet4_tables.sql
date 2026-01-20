-- PolyTool Packet 4 Tables
-- Activity ingestion, position snapshots, and enriched market metadata

-- user_activity: public activity feed for a user
CREATE TABLE IF NOT EXISTS polyttool.user_activity
(
    proxy_wallet String,
    activity_uid String,
    ts DateTime,
    activity_type String,
    token_id Nullable(String),
    condition_id Nullable(String),
    size Nullable(Float64),
    price Nullable(Float64),
    tx_hash Nullable(String),
    raw_json String,
    ingested_at DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(ingested_at)
ORDER BY (proxy_wallet, activity_uid);

-- user_positions_snapshots: snapshot of current positions per user
CREATE TABLE IF NOT EXISTS polyttool.user_positions_snapshots
(
    proxy_wallet String,
    snapshot_ts DateTime,
    token_id String,
    condition_id Nullable(String),
    outcome Nullable(String),
    shares Float64,
    avg_cost Nullable(Float64),
    raw_json String,
    ingested_at DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(ingested_at)
ORDER BY (proxy_wallet, snapshot_ts, token_id);

-- Add missing market metadata columns for upgrades
ALTER TABLE polyttool.markets
    ADD COLUMN IF NOT EXISTS tags Array(String) DEFAULT [];
ALTER TABLE polyttool.markets
    ADD COLUMN IF NOT EXISTS event_title String DEFAULT '';
ALTER TABLE polyttool.markets
    ADD COLUMN IF NOT EXISTS start_date_iso Nullable(DateTime);
ALTER TABLE polyttool.markets
    ADD COLUMN IF NOT EXISTS close_date_iso Nullable(DateTime);

-- Enriched markets view for Grafana
CREATE OR REPLACE VIEW polyttool.markets_enriched AS
WITH
    lowerUTF8(
        concat(
            category,
            ' ',
            event_title,
            ' ',
            question,
            ' ',
            description,
            ' ',
            market_slug,
            ' ',
            arrayStringConcat(tags, ' ')
        )
    ) AS search_text,
    toUInt16OrNull(
        extract(search_text, '(\\d{1,3})\\s*-?\\s*(?:min|mins|minute|minutes|m)\\b')
    ) AS interval_minutes_raw
SELECT
    *,
    multiSearchAnyCaseInsensitive(
        search_text,
        [
            'crypto', 'bitcoin', 'btc', 'eth', 'ethereum',
            'sol', 'solana', 'doge', 'xrp', 'bnb',
            'ada', 'cardano', 'matic', 'polygon',
            'avax', 'avalanche', 'dot', 'polkadot',
            'ltc', 'litecoin'
        ]
    ) AS is_crypto,
    interval_minutes_raw AS interval_minutes,
    interval_minutes_raw IS NOT NULL AS is_intraday
FROM polyttool.markets;

-- Grant SELECT access to grafana_ro user for new tables/views
GRANT SELECT ON polyttool.user_activity TO grafana_ro;
GRANT SELECT ON polyttool.user_positions_snapshots TO grafana_ro;
GRANT SELECT ON polyttool.markets_enriched TO grafana_ro;
