# 2026-04-09 — Wallet Discovery v1 Implementation (Loop A Storage + Plumbing)

**Task:** quick-260409-qeu — Implement Wallet Discovery v1 storage layer (ClickHouse DDL) and Loop A discovery plumbing (leaderboard fetcher, churn detector, scan queue manager, Loop A orchestrator, CLI wiring).

**Status:** COMPLETE — all 54 tests pass, CLI registered, regression clean.

---

## Objective

Ship the Loop A foundation for Wallet Discovery v1:
1. ClickHouse DDL (3 tables: watchlist, leaderboard_snapshots, scan_queue)
2. Python models with lifecycle state machine and transition validation
3. Leaderboard fetcher + churn detector + scan queue manager
4. Loop A orchestrator wiring the above end-to-end
5. CLI: `polytool discovery run-loop-a`
6. 54 deterministic offline tests covering AT-01 through AT-05

**Spec authority:** `docs/specs/SPEC-wallet-discovery-v1.md`

---

## What Was Built

### Task 1: DDL + Models

**`infra/clickhouse/initdb/27_wallet_discovery.sql`**
- `polytool.watchlist` — ReplacingMergeTree on wallet_address + version; 8-value Enum8 lifecycle_state, 3-value ReviewStatus Enum8; GRANT to grafana_ro
- `polytool.leaderboard_snapshots` — MergeTree append-only partitioned by leaderboard_date; stores rank, pnl_usd, volume_usd, is_new flag per fetch run
- `polytool.scan_queue` — ReplacingMergeTree on dedup_key + updated_at; 5-state Enum8 queue_state; lease fields (leased_at, lease_expires_at, lease_owner); GRANT to grafana_ro

**`packages/polymarket/discovery/models.py`**
- `LifecycleState(str, Enum)`: 8 states from spec (discovered, queued, scanned, reviewed, promoted, watched, stale, retired)
- `ReviewStatus(str, Enum)`: pending, approved, rejected
- `QueueState(str, Enum)`: pending, leased, done, failed, dropped
- `VALID_TRANSITIONS` dict encoding the spec state machine
- `InvalidTransitionError(ValueError)` with from/to fields
- `validate_transition(current, target, review_status=None)` — enforces all spec rules:
  - Any transition TO `discovered` is rejected (entry-only state)
  - `reviewed -> promoted` requires `review_status == ReviewStatus.approved` (human gate)
- Dataclasses: `WatchlistRow`, `LeaderboardSnapshotRow`, `ScanQueueRow`

**`packages/polymarket/discovery/clickhouse_writer.py`**
- Follows `_require_password()` fail-fast pattern (CLAUDE.md ClickHouse auth rule)
- `write_watchlist_rows`, `write_leaderboard_snapshot_rows`, `write_scan_queue_rows` — urllib.request POST + Basic auth + JSONEachRow
- `read_latest_snapshot` — reads prior leaderboard snapshot for churn detection

### Task 2: Loop A Plumbing + CLI

**`packages/polymarket/discovery/leaderboard_fetcher.py`**
- `fetch_leaderboard(order_by, time_period, category, max_pages=5, http_client=None)` — paginated fetch stopping on empty page or max_pages (DoS guard)
- `to_snapshot_rows(...)` — converts raw entries to `LeaderboardSnapshotRow` objects; sets `is_new=1` for wallets absent from prior snapshot set

**`packages/polymarket/discovery/churn_detector.py`**
- `ChurnResult`: new_wallets, dropped_wallets, persisting_wallets, rising_wallets (with old/new rank tuples)
- `detect_churn(current_rows, prior_rows)` — first-run safe (empty prior = all wallets new); rising = current_rank < prior_rank, sorted by improvement magnitude

**`packages/polymarket/discovery/scan_queue.py`**
- `ScanQueueManager` — in-memory queue with dedup_key -> ScanQueueRow mapping
- `enqueue()`: idempotent — returns existing item if pending/leased; creates new if terminal or absent
- `lease()`, `complete()`, `fail()` (increments attempt_count), `get_pending()` (priority+created_at ordering)
- `requeue_expired_leases()`: resets leased items past lease_expires_at back to pending
- `flush_to_clickhouse()` / `load_from_clickhouse()` for persistence

**`packages/polymarket/discovery/loop_a.py`**
- `LoopAResult(fetch_run_id, snapshot_ts, rows_fetched, churn, rows_enqueued, dry_run)`
- `run_loop_a(...)` — 10-step orchestration: fail-fast auth -> fetch -> read prior -> churn -> build rows -> write snapshots -> enqueue new -> update watchlist -> return result
- Dry-run skips all ClickHouse reads and writes
- Injectable `fetch_run_id` and `snapshot_ts` for deterministic testing
- Module-level imports enable `patch.object` in tests

**`tools/cli/discovery.py`**
- `main(argv)` with argparse subcommand `run-loop-a`
- Password resolution: `--clickhouse-password` arg OR `CLICKHOUSE_PASSWORD` env var OR fail-fast with error message
- Prints formatted summary (fetch_run_id, snapshot_ts, rows_fetched, churn counts, rows_enqueued)

**`polytool/__main__.py`**
- Registered `discovery_main = _command_entrypoint("tools.cli.discovery")`
- Added `"discovery"` to `_COMMAND_HANDLER_NAMES`
- Added "Wallet Discovery" section to `print_usage()`

### Task 3: Regression + Tests

**`tests/test_wallet_discovery.py`** — 54 tests, all offline/deterministic:
- TestLifecycleStateEnum, TestReviewStatusEnum, TestQueueStateEnum
- TestValidTransitions (6 happy-path transitions)
- TestInvalidTransitions (9 rejection cases including reviewed->promoted without approval)
- TestDataclassFields (field existence for all 3 row types)
- TestLeaderboardFetcher (AT-01: pagination stops at max_pages; empty-page halt)
- TestToSnapshotRows (AT-03: is_new flag logic; determinism with injectable timestamps)
- TestChurnDetector (AT-02/02b/02c: new/dropped/rising detection; first-run all-new)
- TestScanQueueManager (AT-04: enqueue idempotency; lease/complete/fail; pending ordering)
- TestAt05LifecycleFull (AT-05: full lifecycle validated via transition guards)
- TestLoopAOrchestrator (dry-run path; no-new-wallets path; auth fail-fast)

---

## Acceptance Tests

| ID | Description | Result |
|----|-------------|--------|
| AT-01 | Leaderboard fetcher paginates and stops at max_pages | PASS |
| AT-02 | Churn detector: first-run all wallets new | PASS |
| AT-02b | Churn detector: prior snapshot diff (new/dropped/rising) | PASS |
| AT-02c | Churn detector: rising wallets sorted by improvement magnitude | PASS |
| AT-03 | to_snapshot_rows: is_new flag correctly set | PASS |
| AT-04 | ScanQueueManager: enqueue idempotency and lease semantics | PASS |
| AT-05 | Full lifecycle: discovered -> queued -> scanned -> reviewed -> promoted | PASS |

---

## Regression

Baseline after all commits:
- **3896 passed, 0 failed** (excluding pre-existing `test_ris_phase2_cloud_provider_routing.py` failure — AttributeError on `_post_json` attribute, confirmed pre-existing via stash test; logged to deferred items)

---

## Key Decisions

1. **urllib.request + Basic auth** — matched existing `silver_tape_metadata.py` pattern; no new dependencies; explicit per SPEC
2. **Module-level imports in `loop_a.py`** — enables `patch.object(loop_a, "fetch_leaderboard", ...)` in tests for determinism
3. **Injectable `fetch_run_id` / `snapshot_ts`** — eliminates clock dependency in all orchestrator tests
4. **`discovered` as entry-only state** — `validate_transition` rejects any transition TO `discovered`; per spec
5. **`reviewed -> promoted` human gate** — `review_status=ReviewStatus.approved` required; spec AT-05
6. **Dry-run uses `"dummy"` password for ch_kwargs** — CH write functions never called in dry-run, so `_require_password()` is never invoked

---

## Codex Review

Tier: Recommended (ClickHouse write paths). No codex review run — no execution/, kill_switch.py, or order placement code touched. ClickHouse write paths are stdlib HTTP, no py_clob_client. Issues found: N/A.

---

## Open Items

- Loop B (live monitoring / position tracking) is NOT in scope for this task
- Loop C/D not in scope (v1 plan explicitly excludes them)
- `test_ris_phase2_cloud_provider_routing.py` pre-existing failure deferred — out of scope for this task
