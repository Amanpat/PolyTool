-- Phase 1 / Silver tape metadata
-- Canonical record of every Silver tape reconstruction run.
-- Written by batch-reconstruct-silver CLI after each successful reconstruction.
-- Falls back to JSONL if ClickHouse write fails (see silver_tape_metadata.py).
--
-- SCHEMA NOTE:
-- run_id       = unique UUID per single-market reconstruction call
-- batch_run_id = UUID shared across all tokens in one batch-reconstruct-silver run
--                ("" if not a batch run)
-- tape_path    = absolute or relative path to silver_events.jsonl on disk

CREATE TABLE IF NOT EXISTS polytool.tape_metadata
(
    run_id              String,
    tape_path           String,
    tier                LowCardinality(String),
    token_id            String,
    window_start        DateTime64(3, 'UTC'),
    window_end          DateTime64(3, 'UTC'),
    reconstruction_confidence LowCardinality(String),
    warning_count       UInt16,
    source_inputs_json  String,
    generated_at        DateTime64(3, 'UTC'),
    batch_run_id        String
)
ENGINE = ReplacingMergeTree(generated_at)
ORDER BY (tier, token_id, window_start)
SETTINGS index_granularity = 8192;

GRANT SELECT ON polytool.tape_metadata TO grafana_ro;
