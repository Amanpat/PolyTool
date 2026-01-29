-- Market backfill support: tradeable flags for market_tokens

ALTER TABLE polyttool.market_tokens
    ADD COLUMN IF NOT EXISTS enable_order_book Nullable(UInt8);

ALTER TABLE polyttool.market_tokens
    ADD COLUMN IF NOT EXISTS accepting_orders Nullable(UInt8);

GRANT SELECT ON polyttool.market_tokens TO grafana_ro;
