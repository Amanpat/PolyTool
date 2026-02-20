-- Category source markers for market_tokens taxonomy lineage
-- Additive-only migration for environments created before source marker support.

ALTER TABLE polyttool.market_tokens
    ADD COLUMN IF NOT EXISTS category_source String DEFAULT 'none';

ALTER TABLE polyttool.market_tokens
    ADD COLUMN IF NOT EXISTS subcategory_source String DEFAULT 'none';

GRANT SELECT ON polyttool.market_tokens TO grafana_ro;
