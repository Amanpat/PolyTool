-- PolyTool Packet 5.2 Tables
-- Arb feasibility with dynamic fees and slippage

CREATE TABLE IF NOT EXISTS polyttool.arb_feasibility_bucket
(
    proxy_wallet String,
    bucket_type String,                         -- 'day', 'hour', 'week'
    bucket_start DateTime,
    condition_id String,
    gross_edge_est_bps Nullable(Float64),       -- Estimated gross edge, null if unknown
    total_fees_est_usdc Float64,
    total_slippage_est_usdc Float64,
    net_edge_est_bps Nullable(Float64),         -- gross - costs, null if gross unknown
    break_even_notional_usd Nullable(Float64),  -- Notional needed to cover costs
    confidence String,                          -- 'high', 'medium', 'low'
    evidence_json String,
    computed_at DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(computed_at)
ORDER BY (proxy_wallet, bucket_type, bucket_start, condition_id);

GRANT SELECT ON polyttool.arb_feasibility_bucket TO grafana_ro;
