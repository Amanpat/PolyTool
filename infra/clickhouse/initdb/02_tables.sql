-- PolyTool Tables: Users and Trades
-- Packet 2: Username resolution + trade ingestion

-- Users table: stores resolved Polymarket profiles
-- Uses ReplacingMergeTree to handle upserts based on last_updated
CREATE TABLE IF NOT EXISTS polyttool.users
(
    proxy_wallet String,
    username String,
    raw_profile_json String,
    first_seen DateTime DEFAULT now(),
    last_updated DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(last_updated)
ORDER BY (proxy_wallet);

-- User trades table: stores trade history
-- Uses ReplacingMergeTree to handle idempotent inserts based on ingested_at
-- Trade UID is computed as:
--   - The 'id' field from API if present
--   - Otherwise: sha256(proxy_wallet + ts + token_id + side + size + price + transaction_hash + outcome + condition_id)
CREATE TABLE IF NOT EXISTS polyttool.user_trades
(
    proxy_wallet String,
    trade_uid String,
    ts DateTime,
    token_id String,
    condition_id String,
    outcome String,
    side String,
    size Float64,
    price Float64,
    transaction_hash String,
    raw_json String,
    ingested_at DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(ingested_at)
ORDER BY (proxy_wallet, trade_uid);

-- Grant SELECT access to grafana_ro user
GRANT SELECT ON polyttool.users TO grafana_ro;
GRANT SELECT ON polyttool.user_trades TO grafana_ro;
