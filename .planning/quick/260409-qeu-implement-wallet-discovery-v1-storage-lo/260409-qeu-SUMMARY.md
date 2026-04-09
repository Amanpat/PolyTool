---
quick_task: 260409-qeu
subsystem: wallet-discovery
tags: [clickhouse, ddl, loop-a, leaderboard, churn, scan-queue, cli]
tech_stack:
  added: [urllib.request Basic auth, JSONEachRow, ReplacingMergeTree, argparse subcommand]
  patterns: [injectable-params-for-testing, module-level-imports-for-patch, fail-fast-auth]
key_files:
  created:
    - infra/clickhouse/initdb/27_wallet_discovery.sql
    - packages/polymarket/discovery/models.py
    - packages/polymarket/discovery/clickhouse_writer.py
    - packages/polymarket/discovery/leaderboard_fetcher.py
    - packages/polymarket/discovery/churn_detector.py
    - packages/polymarket/discovery/scan_queue.py
    - packages/polymarket/discovery/loop_a.py
    - tools/cli/discovery.py
    - tests/test_wallet_discovery.py
    - docs/dev_logs/2026-04-09_wallet_discovery_v1_impl_a.md
  modified:
    - packages/polymarket/discovery/__init__.py
    - polytool/__main__.py
decisions:
  - urllib.request + Basic auth matching silver_tape_metadata pattern (no new deps)
  - Module-level imports in loop_a.py for patch.object testability
  - Injectable fetch_run_id + snapshot_ts for deterministic orchestrator tests
  - discovered is entry-only state (validate_transition rejects any TO discovered)
  - reviewed->promoted requires review_status=approved (human gate per spec)
metrics:
  duration_minutes: 90
  completed_date: "2026-04-09"
  tasks_completed: 3
  tasks_total: 3
  files_created: 10
  files_modified: 2
  tests_added: 54
  regression_baseline: "3896 passed, 0 failed (pre-existing ris test excluded)"
---

# Quick Task 260409-qeu: Wallet Discovery v1 Storage + Loop A — Summary

**One-liner:** ClickHouse DDL for 3 discovery tables + full Loop A plumbing (leaderboard fetch, churn detection, scan queue, orchestrator, CLI) with 54 deterministic offline tests covering AT-01..AT-05.

## Tasks Completed

| Task | Description | Commit | Status |
|------|-------------|--------|--------|
| 1 | DDL + models + ClickHouse writer | b24641c | DONE |
| 2 | Fetcher + churn + queue + loop_a + CLI | df600ea | DONE |
| 3 | Dev log + regression baseline | 28444e1 | DONE |

## What Was Shipped

### ClickHouse DDL (`infra/clickhouse/initdb/27_wallet_discovery.sql`)
Three tables matching the frozen spec verbatim:
- `polytool.watchlist` — ReplacingMergeTree; 8-state Enum8 lifecycle_state; 3-state ReviewStatus; GRANT to grafana_ro
- `polytool.leaderboard_snapshots` — append-only MergeTree partitioned by leaderboard_date
- `polytool.scan_queue` — ReplacingMergeTree on dedup_key; 5-state queue_state Enum8; lease fields

### Python Models (`packages/polymarket/discovery/models.py`)
- `LifecycleState`, `ReviewStatus`, `QueueState` enums
- `VALID_TRANSITIONS` dict encoding spec state machine
- `validate_transition()` with two special rules: entry-only `discovered`, human-gated `reviewed -> promoted`
- `WatchlistRow`, `LeaderboardSnapshotRow`, `ScanQueueRow` dataclasses

### ClickHouse Writer (`packages/polymarket/discovery/clickhouse_writer.py`)
- fail-fast `_require_password()` enforcing CLAUDE.md ClickHouse auth rule
- Write functions for all 3 tables (urllib.request + Basic auth + JSONEachRow)
- `read_latest_snapshot` for churn detection

### Leaderboard Fetcher (`packages/polymarket/discovery/leaderboard_fetcher.py`)
- Paginated fetch with empty-page halt and max_pages DoS guard
- `to_snapshot_rows()` with injectable timestamps and `is_new` flag from prior wallet set

### Churn Detector (`packages/polymarket/discovery/churn_detector.py`)
- `ChurnResult`: new, dropped, persisting, rising wallets
- First-run safe (empty prior = all new); rising sorted by improvement magnitude

### Scan Queue Manager (`packages/polymarket/discovery/scan_queue.py`)
- In-memory queue with dedup_key semantics and lease/expiry enforcement
- `enqueue()` idempotent on active items; `requeue_expired_leases()` for stale leases
- `flush_to_clickhouse()` and `load_from_clickhouse()` for persistence

### Loop A Orchestrator (`packages/polymarket/discovery/loop_a.py`)
- 10-step orchestration: fail-fast auth -> fetch -> read prior -> churn -> rows -> write -> enqueue -> watchlist -> return
- Dry-run skips all CH I/O
- Injectable `fetch_run_id` + `snapshot_ts` for determinism

### CLI (`tools/cli/discovery.py` + `polytool/__main__.py`)
- `polytool discovery run-loop-a` with full flag set
- Password: `--clickhouse-password` arg or `CLICKHOUSE_PASSWORD` env var; fail-fast if neither
- Dry-run flag for offline testing

## Acceptance Tests

| ID | Description | Result |
|----|-------------|--------|
| AT-01 | Leaderboard fetcher paginates and stops at max_pages | PASS |
| AT-02 | Churn detector: first-run all wallets new | PASS |
| AT-02b | Churn detector: prior snapshot diff | PASS |
| AT-02c | Churn detector: rising wallets by magnitude | PASS |
| AT-03 | to_snapshot_rows is_new flag | PASS |
| AT-04 | ScanQueueManager dedup + lease semantics | PASS |
| AT-05 | Full lifecycle: discovered -> ... -> promoted | PASS |

## Regression

**3896 passed, 0 failed** (54 new tests pass; 1 pre-existing `test_ris_phase2_cloud_provider_routing.py` failure excluded — `AttributeError: _post_json` predating this task, confirmed via stash test).

## Deviations from Plan

None — plan executed exactly as written. All files implemented per SPEC-wallet-discovery-v1.md. No architectural changes required.

## Known Stubs

None — all data paths are wired. The CLI `--dry-run` flag is intentional (not a stub) and documented.

## Threat Flags

None — no new network endpoints, no FastAPI routes, no auth path changes. ClickHouse write paths use the established urllib.request + Basic auth pattern. The `discovery` CLI command requires password via env var (fail-fast).

## Self-Check

- [x] `infra/clickhouse/initdb/27_wallet_discovery.sql` — exists
- [x] `packages/polymarket/discovery/models.py` — exists
- [x] `packages/polymarket/discovery/clickhouse_writer.py` — exists
- [x] `packages/polymarket/discovery/leaderboard_fetcher.py` — exists
- [x] `packages/polymarket/discovery/churn_detector.py` — exists
- [x] `packages/polymarket/discovery/scan_queue.py` — exists
- [x] `packages/polymarket/discovery/loop_a.py` — exists
- [x] `tools/cli/discovery.py` — exists
- [x] `tests/test_wallet_discovery.py` — exists, 54 passed
- [x] Commit b24641c — exists
- [x] Commit df600ea — exists
- [x] Commit 28444e1 — exists

## Self-Check: PASSED
