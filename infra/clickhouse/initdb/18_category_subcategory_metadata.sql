-- Category taxonomy metadata columns for market_tokens
-- Additive-only migration for environments created before category taxonomy support.

ALTER TABLE polyttool.market_tokens
    ADD COLUMN IF NOT EXISTS category String DEFAULT '';

ALTER TABLE polyttool.market_tokens
    ADD COLUMN IF NOT EXISTS subcategory String DEFAULT '';

GRANT SELECT ON polyttool.market_tokens TO grafana_ro;
