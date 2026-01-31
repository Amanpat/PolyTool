-- LLM Research Packet v1 export history

CREATE TABLE IF NOT EXISTS polyttool.user_dossier_exports
(
    export_id String,
    proxy_wallet String,
    user_input String,
    username String,
    username_slug String,
    artifact_path String,
    generated_at DateTime DEFAULT now(),
    window_days Int32,
    window_start DateTime,
    window_end DateTime,
    max_trades Int32,
    trades_count Int32,
    activity_count Int32,
    positions_count Int32,
    mapping_coverage Float64,
    liquidity_ok_count Int32,
    liquidity_total_count Int32,
    usable_liquidity_rate Float64,
    pricing_snapshot_ratio Float64,
    pricing_confidence String,
    detectors_json String CODEC(ZSTD),
    dossier_json String CODEC(ZSTD),
    memo_md String CODEC(ZSTD),
    anchor_trade_uids Array(String),
    notes String DEFAULT ''
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(generated_at)
ORDER BY (proxy_wallet, generated_at);

ALTER TABLE polyttool.user_dossier_exports
    ADD COLUMN IF NOT EXISTS username String;

ALTER TABLE polyttool.user_dossier_exports
    ADD COLUMN IF NOT EXISTS username_slug String;

ALTER TABLE polyttool.user_dossier_exports
    ADD COLUMN IF NOT EXISTS artifact_path String;

CREATE OR REPLACE VIEW polyttool.user_dossier_exports_latest AS
SELECT
    proxy_wallet,
    export_id,
    user_input,
    username,
    username_slug,
    artifact_path,
    latest_generated_at AS generated_at,
    window_days,
    window_start,
    window_end,
    max_trades,
    trades_count,
    activity_count,
    positions_count,
    mapping_coverage,
    liquidity_ok_count,
    liquidity_total_count,
    usable_liquidity_rate,
    pricing_snapshot_ratio,
    pricing_confidence,
    detectors_json,
    dossier_json,
    memo_md,
    anchor_trade_uids,
    notes
FROM
(
    SELECT
        proxy_wallet,
        argMax(export_id, generated_at) AS export_id,
        argMax(user_input, generated_at) AS user_input,
        argMax(username, generated_at) AS username,
        argMax(username_slug, generated_at) AS username_slug,
        argMax(artifact_path, generated_at) AS artifact_path,
        max(generated_at) AS latest_generated_at,
        argMax(window_days, generated_at) AS window_days,
        argMax(window_start, generated_at) AS window_start,
        argMax(window_end, generated_at) AS window_end,
        argMax(max_trades, generated_at) AS max_trades,
        argMax(trades_count, generated_at) AS trades_count,
        argMax(activity_count, generated_at) AS activity_count,
        argMax(positions_count, generated_at) AS positions_count,
        argMax(mapping_coverage, generated_at) AS mapping_coverage,
        argMax(liquidity_ok_count, generated_at) AS liquidity_ok_count,
        argMax(liquidity_total_count, generated_at) AS liquidity_total_count,
        argMax(usable_liquidity_rate, generated_at) AS usable_liquidity_rate,
        argMax(pricing_snapshot_ratio, generated_at) AS pricing_snapshot_ratio,
        argMax(pricing_confidence, generated_at) AS pricing_confidence,
        argMax(detectors_json, generated_at) AS detectors_json,
        argMax(dossier_json, generated_at) AS dossier_json,
        argMax(memo_md, generated_at) AS memo_md,
        argMax(anchor_trade_uids, generated_at) AS anchor_trade_uids,
        argMax(notes, generated_at) AS notes
    FROM polyttool.user_dossier_exports
    GROUP BY proxy_wallet
);

GRANT SELECT ON polyttool.user_dossier_exports TO grafana_ro;
GRANT SELECT ON polyttool.user_dossier_exports_latest TO grafana_ro;
