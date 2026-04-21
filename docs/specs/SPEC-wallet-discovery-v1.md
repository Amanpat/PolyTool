# SPEC-wallet-discovery-v1: Wallet Discovery v1 — Contract

## Status

**Frozen** — docs-only contract as of 2026-04-09. No code, migrations, tests, or
workflow changes are included in this packet. Implementation is pending.

**Parent references**:
- `docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md` (governing roadmap)
- `docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md` (LLM policy table)
- `docs/obsidian-vault/08-Research/01-Wallet-Discovery-Pipeline.md` (four-loop architecture)
- `docs/obsidian-vault/08-Research/06-Wallet-Discovery-Roadmap.md` (full 7-phase roadmap)
- `docs/obsidian-vault/09-Decisions/Decision - Roadmap Narrowed to V1.md`
- `docs/obsidian-vault/09-Decisions/Decision - Watchlist ClickHouse Storage.md`
- `docs/obsidian-vault/10-Session-Notes/2026-04-09 Architect Review Assessment.md`

**Date**: 2026-04-09

---

## V1 Scope

Wallet Discovery v1 covers exactly these four capabilities. Nothing else.

### a) Loop A — Leaderboard Discovery

24-hour scheduled fetch from the Polymarket leaderboard API:

```
GET https://data-api.polymarket.com/v1/leaderboard
```

Each fetch run:
1. Pages through leaderboard results (multi-page, up to configurable max).
2. Persists raw rows into `leaderboard_snapshots` (see table contract below).
3. Runs churn detection: compares current snapshot to previous snapshot at the
   same `(order_by, time_period, category)` key to identify new wallets, rising
   wallets, and dropped wallets. New wallets flagged with `is_new=1`.
4. Populates `scan_queue` with newly discovered wallets from churn detection.

The DAY vs ALL comparison (comparing 24-hour top performers against all-time
rankings) is the primary signal for detecting rapid-rise wallets worth scanning.

### b) ClickHouse Table Contracts

Three tables are defined: `watchlist`, `leaderboard_snapshots`, `scan_queue`.
See **ClickHouse Table Contracts** section below for exact DDL.

### c) Unified `python -m polytool scan <address>` with `--quick`

The existing `scan` CLI surface is extended with a `--quick` flag:

- `--quick`: Run a fast scan with no LLM calls. Outputs MVF vector, existing
  detectors, and PnL data. Does not call any cloud LLM endpoint under any
  condition. This is a hard guarantee, not a configuration option.
- Without `--quick`: Existing scan behavior unchanged.
- Input: wallet address (0x-prefixed) or handle.
- Output: extends the current scan artifact schema with an `mvf` block when
  `--quick` is specified.

### d) MVF (Multi-Variate Fingerprint) Computation

A deterministic Python computation (no cloud LLM calls) that produces an
11-dimensional fingerprint vector for a wallet based on its trade history.

**Dimensions (v1 definition)**:
1. `win_rate` — fraction of resolved positions that are WIN or PROFIT_EXIT
2. `avg_hold_duration_hours` — mean position hold time in hours
3. `median_entry_price` — median entry price across all positions
4. `market_concentration` — Herfindahl index over market slugs (1 = one market, 0 = fully diversified)
5. `category_entropy` — Shannon entropy of trades across Polymarket categories
6. `avg_position_size_usdc` — mean notional size per position in USDC
7. `trade_frequency_per_day` — total trades divided by observation window in days
8. `late_entry_rate` — fraction of positions entered in the final 20% of a market's life
9. `dca_score` — fraction of markets where more than one entry was made (DCA-style behavior)
10. `resolution_coverage_rate` — fraction of positions with non-UNKNOWN resolution
11. `maker_taker_ratio` — fraction of trades that are maker-side (optional: may be null if data unavailable)

Each dimension is a float. Ranges are defined per-dimension in the implementation
spec. The output includes a metadata block with `wallet_address`,
`computation_timestamp`, and `input_trade_count`.

**Out of scope for v1**: LLM interpretation of MVF, MVF comparison across wallets,
MVF-driven auto-promotion.

---

## Non-Goals for v1

The following are explicitly NOT in v1 scope. Each is future intent with named
blockers (see the Blockers section below).

- **Loop B** — live wallet monitoring via Alchemy WebSocket
- **Loop C** — deep analysis and cloud LLM hypothesis generation for wallets
- **Loop D** — platform-wide anomaly detection via CLOB WebSocket
- **Insider scoring** — binomial test, pre-event trading score (requires per-bucket
  calibration; single averaged-p0 binomial test is mathematically incorrect per
  architect review 2026-04-09)
- **Exemplar selection** — trade annotation for LLM context window
- **Cloud LLM calls for wallet analysis** — current policy authorizes Tier 1 free
  cloud APIs (Gemini Flash, DeepSeek V3) for RIS evaluation gate scoring ONLY
  (per PLAN_OF_RECORD Section 0 and Master Roadmap v5.1 LLM Policy table).
  Wallet analysis via cloud LLM requires a PLAN_OF_RECORD update to extend Tier 1
  policy beyond RIS. No AI agent should extend this policy autonomously.
- **Auto-promotion to watchlist** — v1 requires a human review gate before any
  wallet reaches `promoted` or `watched` state. No code path should bypass this.
- **n8n workflow integration for discovery** — broad n8n orchestration remains a
  Phase 3 target; the scoped RIS n8n pilot (ADR 0013) does not extend to discovery
- **Docker service definitions for Loop B / Loop D**
- **Copy-trading system**
- **SimTrader closed-loop testing of discovery hypotheses**

---

## Blockers for Phases Beyond v1

Each future capability has a named prerequisite that must be met before
implementation begins.

| Capability | Blocker |
|------------|---------|
| Cloud LLM for wallet analysis (Loop C) | PLAN_OF_RECORD Section 0 update extending Tier 1 policy beyond RIS; human decision required |
| Loop B (Alchemy WebSocket monitoring) | Alchemy account creation; proof-of-feasibility for dynamic topic filter updates at runtime; CU consumption verification (cost model) |
| Loop D (CLOB anomaly detection) | CLOB WebSocket connectivity test; managed subscription prototype for multi-market streaming; anomaly detector threshold calibration data |
| Insider scoring | Per-bucket calibration test design; single averaged-p0 binomial test identified as mathematically incorrect in architect review 2026-04-09; correct statistical model must be defined first |
| Auto-promotion to watchlist | Evidence-quality threshold definition; human-gate removal justification; operator sign-off |
| n8n integration for discovery | Broad n8n orchestration is Phase 3 target (ADR 0013 scoped to RIS only); no discovery workflow until Phase 3 milestone |

---

## ClickHouse Table Contracts

All three tables follow the project's ClickHouse conventions:
- `ReplacingMergeTree(updated_at)` for mutable state (one current row per key)
- `MergeTree()` for append-only facts
- Engine, ORDER BY, and column names are the contract; index tuning is an
  implementation detail.

Reference: `infra/clickhouse/initdb/` for naming and engine conventions.

### Table: `watchlist`

```sql
CREATE TABLE IF NOT EXISTS watchlist
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
```

**Semantics**:
- One current row per wallet. `ReplacingMergeTree` collapses duplicate `wallet_address`
  rows on merge, keeping the row with the latest `updated_at`.
- No auto-promotion. `review_status` must be manually set to `'approved'` by a human
  operator before `lifecycle_state` can advance to `'promoted'`. Application-level
  validation enforces this.
- `source` values: `'loop_a'`, `'manual'`, `'loop_d'` (loop_d is future intent).
- `priority` range: 1 (highest) to 5 (lowest); default 3.

### Table: `leaderboard_snapshots`

```sql
CREATE TABLE IF NOT EXISTS leaderboard_snapshots
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
```

**Semantics**:
- Append-only raw facts. Each fetch run appends a batch of rows. Historical
  snapshots are never mutated.
- Dedup key: `(snapshot_ts, order_by, time_period, category, proxy_wallet)`.
  Enforced by ORDER BY; re-inserts with identical key are idempotent under
  MergeTree dedup after `OPTIMIZE TABLE`.
- `order_by` example values: `'PNL'`, `'VOL'`
- `time_period` example values: `'DAY'`, `'WEEK'`, `'MONTH'`, `'ALL'`
- `category` example values: `'OVERALL'`, `'POLITICS'`, `'SPORTS'`, `'CRYPTO'`
- `is_new = 1` means the wallet was not present in the most recent prior snapshot
  at the same `(order_by, time_period, category)` key.

### Table: `scan_queue`

```sql
CREATE TABLE IF NOT EXISTS scan_queue
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
```

**Semantics**:
- Only one open item per `dedup_key`. `ReplacingMergeTree` keeps the latest
  `updated_at` row per `dedup_key`.
- `dedup_key` format: `'{source}:{wallet_address}'`, e.g. `'loop_a:0xabc...'`.
  A wallet from a given source is deduplicated against its current open item.
- A wallet can be re-queued after its current item reaches a terminal state
  (`done`, `failed`, `dropped`): a new row with a new `queue_id` and
  `queue_state='pending'` is inserted.
- Lease expiry is not enforced by ClickHouse. The consumer application queries
  `WHERE queue_state = 'pending' AND available_at <= now()` and re-leases items
  whose `lease_expires_at` has passed.
- `attempt_count` is incremented on each re-queue after failure.

---

## Wallet Lifecycle State Machine

### States

```
discovered -> queued -> scanned -> reviewed -> promoted -> watched
                                                               |
                                                           stale <-> queued
                                                           stale -> retired
                any state -> retired (operator manual)
```

**State descriptions**:

| State | Meaning |
|-------|---------|
| `discovered` | Wallet seen in leaderboard snapshot; not yet in scan queue |
| `queued` | Added to `scan_queue`; awaiting scan |
| `scanned` | Scan completed; MVF and detectors computed; awaiting human review |
| `reviewed` | Human operator has reviewed scan output |
| `promoted` | Human approved; wallet elevated to operational tracking (v1 max state) |
| `watched` | Active Loop B monitoring (future — not operationally reachable in v1) |
| `stale` | No activity detected for configurable threshold (e.g., 30 days) |
| `retired` | Permanently removed from active tracking |

### Allowed Transitions

| From | To | Trigger |
|------|----|---------|
| `discovered` | `queued` | Scan queue picks up wallet |
| `queued` | `scanned` | Scan completes successfully |
| `queued` | `queued` | Scan fails; re-queued with incremented `attempt_count` |
| `scanned` | `reviewed` | Human operator reviews scan output |
| `reviewed` | `promoted` | Human approves; `review_status` must be `'approved'` |
| `reviewed` | `retired` | Human rejects; `review_status` set to `'rejected'` |
| `promoted` | `watched` | Operator activates for Loop B monitoring (future, not in v1) |
| `watched` | `stale` | No activity detected for configurable threshold |
| `stale` | `queued` | Rescan triggered |
| `stale` | `retired` | Operator retires stale wallet |
| any state | `retired` | Operator manual retirement |

### Invalid Transitions (explicitly rejected)

These transitions MUST be rejected by application-level validation, not ClickHouse:

| Attempted | Reason |
|-----------|--------|
| `discovered -> promoted` | Skips mandatory scan and review gates |
| `discovered -> watched` | Skips all gates |
| `queued -> promoted` | Skips scan and review gates |
| `scanned -> promoted` | **Skips human review gate — this is mandatory in v1** |
| `scanned -> watched` | Skips review gate and Loop B activation |
| any state -> `discovered` | `discovered` is an entry-only state; wallets cannot be "rediscovered" once in the system |

**Note on `watched` in v1**: The `watched` state exists in the schema for forward
compatibility, but is not operationally reachable in v1 because Loop B is out of
scope. Wallets max out at `promoted` in v1. Code must not allow the transition
`promoted -> watched` until Loop B is implemented and explicitly enabled.

---

## Deterministic Acceptance Tests

These are test _specifications_, not test code. The implementation phase is
responsible for writing actual test code conforming to these contracts. Each
test must pass deterministically (no network, no clock, no randomness) using
fixtures and mocks.

### AT-01: Leaderboard Pagination Fixture

- **Given**: A mock leaderboard API returning 3 pages of 50 entries each (150
  entries total), with entries numbered rank 1-150, all having non-empty
  `proxy_wallet` fields.
- **When**: `fetch_leaderboard(max_pages=3)` is called against the mock.
- **Then**: 150 entries are returned.
- **And**: Entries are ordered by rank (1 to 150) with no duplicates.
- **And**: All returned entries have non-empty `proxy_wallet` fields.

### AT-02: Churn Detection

- **Given**: Snapshot T-1 containing wallets `[A, B, C]` at `(order_by='PNL',
  time_period='DAY', category='OVERALL')`.
- **And**: Snapshot T containing wallets `[B, C, D]` at the same key.
- **When**: Churn detection runs comparing T against T-1.
- **Then**: Wallet `D` is flagged as `is_new=1` in snapshot T rows.
- **And**: Wallet `A` is detected as dropped (present in T-1, absent in T) and
  is recorded in the churn report.

### AT-03: Snapshot Idempotency

- **Given**: An identical leaderboard response fetched twice with the same
  `snapshot_ts`, `order_by`, `time_period`, and `category`.
- **When**: Both batches are inserted into `leaderboard_snapshots`.
- **Then**: After `OPTIMIZE TABLE leaderboard_snapshots FINAL`, the table contains
  exactly one set of rows (not duplicated) for that `snapshot_ts`/key combination.

### AT-04: Queue Dedup and Lease Behavior

- **Dedup test**:
  - Given: wallet `0xABC` already in `scan_queue` with `queue_state='pending'` and
    `dedup_key='loop_a:0xABC'`.
  - When: A second insert arrives with the same `dedup_key`.
  - Then: After `OPTIMIZE TABLE scan_queue FINAL`, only one row exists for
    `dedup_key='loop_a:0xABC'`.

- **Lease expiry test**:
  - Given: A pending item is leased (`queue_state='leased'`,
    `lease_expires_at=now()+300`).
  - When: `lease_expires_at` passes (test hook: inject a past timestamp).
  - Then: The consumer's polling query (`WHERE queue_state='pending' AND
    available_at <= now()`) does not return the item while leased and within TTL.
  - And: After expiry, the application re-queues the item with a new `updated_at`,
    making it available for re-lease.

### AT-05: Invalid Lifecycle Transition Rejection

- **Given**: A wallet in `watchlist` with `lifecycle_state='discovered'`.
- **When**: The application attempts to transition `lifecycle_state` directly to
  `'promoted'`.
- **Then**: The application-layer validator rejects the transition with an error.
- **And**: The error message names the invalid transition (e.g.,
  `"Invalid transition: discovered -> promoted"`).
- **And**: The `watchlist` row is not updated.

### AT-06: Unified Scan `--quick` No-LLM Guarantee

- **Given**: `python -m polytool scan <address> --quick` is invoked with a valid
  wallet address and a mocked trade history fixture.
- **When**: The scan completes.
- **Then**: Zero HTTP calls are made to any cloud LLM endpoint (Gemini, DeepSeek,
  OpenAI, Anthropic). This must be verified via request-intercepting test fixtures,
  not merely by inspection.
- **And**: The output contains: MVF vector block, existing detector results, and
  PnL data.
- **And**: The output does NOT contain any LLM-generated hypothesis text.

### AT-07: MVF Fixture Output Shape

- **Given**: A synthetic dossier JSON with a known set of 50 resolved trade
  records (fixture defined once and pinned).
- **When**: MVF computation runs against the fixture.
- **Then**: The output contains all 11 defined dimensions (dimensions 1-10
  required; dimension 11 `maker_taker_ratio` may be `null` if data unavailable).
- **And**: Each non-null dimension is a float within its documented range.
- **And**: The output includes a metadata block with `wallet_address`,
  `computation_timestamp`, and `input_trade_count=50`.
- **And**: Running the same computation twice against the same fixture produces
  identical output (determinism).

---

## Database Architecture Alignment

Wallet Discovery v1 writes live discovery state (watchlist, leaderboard_snapshots,
scan_queue) to ClickHouse, consistent with the project's one-sentence rule:

> **ClickHouse handles all live streaming writes. DuckDB handles all historical
> Parquet reads.**

Discovery tables are live-updating state, not historical Parquet bulk. They belong
in ClickHouse. This does not alter DuckDB's role: DuckDB continues to handle pmxt
and Jon-Becker Parquet reads, Silver tape reconstruction, and SimTrader sweep
analytics. The two databases do not share data and do not communicate.

---

## Cross-References

| Document | Role |
|----------|------|
| `docs/obsidian-vault/08-Research/01-Wallet-Discovery-Pipeline.md` | Four-loop architecture: full design context |
| `docs/obsidian-vault/08-Research/06-Wallet-Discovery-Roadmap.md` | Full 7-phase roadmap; treated as design doc, not a delivery commitment |
| `docs/obsidian-vault/09-Decisions/Decision - Roadmap Narrowed to V1.md` | Director decision to narrow scope to v1 |
| `docs/obsidian-vault/09-Decisions/Decision - Watchlist ClickHouse Storage.md` | Decision to use ClickHouse for watchlist/queue/snapshot tables |
| `docs/obsidian-vault/10-Session-Notes/2026-04-09 Architect Review Assessment.md` | Architect review identifying insider scoring flaw and scope blockers |
| `docs/specs/SPEC-wallet-scan-v0.md` | Existing wallet-scan v0 spec; v1 discovery extends the `scan` surface |
| `docs/features/wallet-scan-v0.md` | Existing wallet-scan v0 feature doc; predecessor to v1 |
| `docs/features/wallet-discovery-v1.md` | Feature stub for this v1 contract |
| `docs/PLAN_OF_RECORD.md` | LLM policy (Section 0), mission constraints |
| `docs/ARCHITECTURE.md` | Database architecture rule; discovery tables in ClickHouse |
| `docs/ROADMAP.md` | Wallet Discovery v1 milestone entry |
