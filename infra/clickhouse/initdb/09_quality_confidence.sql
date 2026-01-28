-- PolyTool Packet 5.3.2 Tables
-- Quality & Confidence Layer

-- Add pricing confidence fields to user_pnl_bucket
-- Note: Using IF NOT EXISTS for idempotent migrations
ALTER TABLE polyttool.user_pnl_bucket
    ADD COLUMN IF NOT EXISTS pricing_snapshot_ratio Float64 DEFAULT 0.0;

ALTER TABLE polyttool.user_pnl_bucket
    ADD COLUMN IF NOT EXISTS pricing_confidence String DEFAULT 'LOW';

-- Add liquidity confidence fields to arb_feasibility_bucket
ALTER TABLE polyttool.arb_feasibility_bucket
    ADD COLUMN IF NOT EXISTS liquidity_confidence String DEFAULT 'low';

ALTER TABLE polyttool.arb_feasibility_bucket
    ADD COLUMN IF NOT EXISTS priced_legs Int32 DEFAULT 0;

ALTER TABLE polyttool.arb_feasibility_bucket
    ADD COLUMN IF NOT EXISTS missing_legs Int32 DEFAULT 0;

ALTER TABLE polyttool.arb_feasibility_bucket
    ADD COLUMN IF NOT EXISTS confidence_reason String DEFAULT '';

ALTER TABLE polyttool.arb_feasibility_bucket
    ADD COLUMN IF NOT EXISTS depth_100_ok UInt8 DEFAULT 0;

ALTER TABLE polyttool.arb_feasibility_bucket
    ADD COLUMN IF NOT EXISTS depth_500_ok UInt8 DEFAULT 0;

-- Grant permissions
GRANT SELECT ON polyttool.user_pnl_bucket TO grafana_ro;
GRANT SELECT ON polyttool.arb_feasibility_bucket TO grafana_ro;
