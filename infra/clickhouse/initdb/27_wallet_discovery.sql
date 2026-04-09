-- Wallet Discovery v1 — ClickHouse table contracts
-- SPEC: docs/specs/SPEC-wallet-discovery-v1.md (frozen 2026-04-09)
-- Three tables: watchlist, leaderboard_snapshots, scan_queue

-- ---------------------------------------------------------------------------
-- Table: polytool.watchlist
-- One current row per wallet. ReplacingMergeTree collapses on updated_at.
-- No auto-promotion: review_status must be manually set to 'approved' before
-- lifecycle_state can advance to 'promoted'. Application-layer enforced.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS polytool.watchlist
(
    wallet_address    String,
    lifecycle_state   Enum8(
                          'discovered' = 1,
                          'queued'     = 2,
                          'scanned'    = 3,
                          'reviewed'   = 4,
                          'promoted'   = 5,
                          'watched'    = 6,
                          'stale'      = 7,
                          'retired'    = 8
                      ),
    review_status     Enum8(
                          'pending'   = 1,
                          'approved'  = 2,
                          'rejected'  = 3
                      ),
    priority          UInt8        DEFAULT 3,
    source            String,
    reason            String       DEFAULT '',
    last_scan_run_id  Nullable(String),
    last_scanned_at   Nullable(DateTime),
    last_activity_at  Nullable(DateTime),
    metadata_json     String       DEFAULT '{}',
    updated_at        DateTime     DEFAULT now()
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (wallet_address);

GRANT SELECT ON polytool.watchlist TO grafana_ro;

-- ---------------------------------------------------------------------------
-- Table: polytool.leaderboard_snapshots
-- Append-only raw facts. Each fetch run appends a batch of rows.
-- Dedup key: (snapshot_ts, order_by, time_period, category, proxy_wallet).
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS polytool.leaderboard_snapshots
(
    snapshot_ts       DateTime,
    fetch_run_id      String,
    order_by          String,
    time_period       String,
    category          String,
    rank              UInt32,
    proxy_wallet      String,
    username          String       DEFAULT '',
    pnl               Float64,
    volume            Float64,
    is_new            UInt8        DEFAULT 0,
    raw_payload_json  String       DEFAULT '{}'
)
ENGINE = MergeTree()
ORDER BY (snapshot_ts, order_by, time_period, category, proxy_wallet);

GRANT SELECT ON polytool.leaderboard_snapshots TO grafana_ro;

-- ---------------------------------------------------------------------------
-- Table: polytool.scan_queue
-- Only one open item per dedup_key. ReplacingMergeTree keeps latest updated_at.
-- Lease expiry is application-enforced (not ClickHouse-enforced).
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS polytool.scan_queue
(
    queue_id          String       DEFAULT generateUUIDv4(),
    dedup_key         String,
    wallet_address    String,
    source            String,
    source_ref        String       DEFAULT '',
    priority          UInt8        DEFAULT 3,
    queue_state       Enum8(
                          'pending'  = 1,
                          'leased'   = 2,
                          'done'     = 3,
                          'failed'   = 4,
                          'dropped'  = 5
                      ),
    available_at      DateTime     DEFAULT now(),
    leased_at         Nullable(DateTime),
    lease_expires_at  Nullable(DateTime),
    lease_owner       Nullable(String),
    attempt_count     UInt8        DEFAULT 0,
    last_error        Nullable(String),
    created_at        DateTime     DEFAULT now(),
    updated_at        DateTime     DEFAULT now()
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (dedup_key);

GRANT SELECT ON polytool.scan_queue TO grafana_ro;
