-- Category taxonomy metadata columns for market_tokens
-- Additive-only migration for environments created before category taxonomy support.

ALTER TABLE polytool.market_tokens
    ADD COLUMN IF NOT EXISTS category String DEFAULT '';

ALTER TABLE polytool.market_tokens
    ADD COLUMN IF NOT EXISTS subcategory String DEFAULT '';

GRANT SELECT ON polytool.market_tokens TO grafana_ro;
