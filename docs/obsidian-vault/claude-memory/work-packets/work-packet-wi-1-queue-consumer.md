---
title: "Work Packet — WI-1 Queue Consumer + Arg-Seam Fix"
type: work_packet
status: active
source_zone: claude_memory
last_updated: 2026-05-29
lifecycle: draft
tags: [work-packet, wallet-discovery, ingestion, queue-consumer]
target_agent: claude-code
acceptance_criteria:
  - See Definition of Done
---
# Work Packet — WI-1 Queue Consumer + Arg-Seam Fix

**Status: DRAFT — pending architect review.** The keystone packet: without it, discovery populates a queue nothing drains.

## Goal
Build the consumer that drains `scan_queue` → runs `wallet-scan` on each leased address → produces a dossier → ingests findings into RIS → marks the queue row complete/fail. Fix the `--wallet`/`--user` argument mismatch so raw addresses flow through. Collapse ReplacingMergeTree to latest state on queue load. Preserve maker/taker **only if the scan source already returns it**.

## Context (audit evidence)
- Enqueue/lease exist, no drain: `packages/polymarket/discovery/scan_queue.py` (`ScanQueueManager.enqueue/lease/complete/fail/requeue_expired_leases`); `load_from_clickhouse` reads ordered by dedup key but does not collapse RMT versions.
- `tools/cli/discovery.py :: _run_loop_a` stops at enqueue + watchlist insert; no consumer.
- Arg break: `tools/cli/wallet_scan.py :: _default_scan_callable` (lines 181-190) passes `--wallet`; `tools/cli/scan.py` parser accepts `--user` only (lines 1731-1772).
- maker/taker dropped: `packages/polymarket/llm_research_packets.py` position export (lines 1600-1639); `infra/clickhouse/initdb/02_tables.sql :: user_trades` lacks maker/taker columns.

## Scope
1. **Arg-seam fix (smallest blocker, do first).** Reconcile the discovery→scan call so a raw wallet address is accepted. Either make `scan` accept `--wallet` as an alias for the address path, or change `_default_scan_callable` to pass `--user`, whichever matches `scan`'s actual identity semantics. Add a regression test that a raw address scans through the default callable (no injected mock).
2. **Queue consumer.** New consumer that: leases a pending row (honor existing lease/expiry/requeue semantics) → invokes `wallet-scan` (or the scan callable) on the address → on success, runs dossier extraction + `ingest_dossier_findings` → marks `complete`; on failure, marks `fail` and lets expired-lease requeue handle retry within attempt limits. Expose via CLI, e.g. `discovery run-worker` (separate invocation from `run-loop-a`).
3. **RMT latest-state collapse.** `load_from_clickhouse` (or the consumer's pending-selection path) must resolve `scan_queue` to latest state per dedup key (ReplacingMergeTree), so a wallet isn't leased on a stale version.
4. **maker/taker preserve rider (bounded).** Investigate whether the scan's data-api responses carry a maker/taker indicator per fill. **If present:** preserve it into scan output + add a `maker_taker` (or equivalent) column to `user_trades` DDL. **If absent:** document the finding in the dev log and leave a clearly-marked TODO referencing the deferred insider/on-chain path. Do NOT add on-chain log fetching to satisfy this.

## Steps
1. Fix and test the arg seam.
2. Implement the consumer with lease→scan→dossier→ingest→complete/fail.
3. Add RMT latest-state resolution on queue read.
4. Investigate + (conditionally) preserve maker/taker.
5. Wire the `run-worker` CLI; keep discovery and worker as separate commands.
6. Manual end-to-end smoke + dev log.

## Definition of Done
- [x] Raw wallet address scans through the default (non-mocked) path. — live smoke: `0x84cf…2f63` resolved via `--user` as wallet.
- [x] Consumer leases a pending wallet, runs the scan, writes a dossier, ingests source doc + claims into the knowledge store, marks the row complete. — `ScanWorker` in `packages/polymarket/discovery/scan_worker.py`.
- [x] Failure path marks `fail`; expired leases requeue within attempt limits. — covered by `tests/test_scan_worker.py`; worker adds a max-attempts (5) dead-letter ceiling.
- [x] Queue read returns latest RMT state per dedup key. — `load_from_clickhouse` now `SELECT ... FINAL ORDER BY dedup_key, updated_at` (version column confirmed `ReplacingMergeTree(updated_at)`).
- [x] maker/taker: dev-log note documents it is **unavailable** from the Data API (`/trades` has `side` only) and defers it to the raw-Jon-parquet/DuckDB path; no on-chain code added.
- [x] `discovery run-worker` CLI exists, separate from `run-loop-a`.
- [x] Manual smoke documented; dev log at `docs/dev_logs/2026-05-31_wi-1-queue-consumer.md`.

**COMPLETED 2026-05-31.** 142 tests pass (0 new failures). Live end-to-end smoke PASS against running API+ClickHouse (queue done → dossier → KS +2 docs/+2 claims → watchlist `scanned`). Watchlist lifecycle discovered→scanned was NOT in the reused path and is now set by the worker (within scope; no tier logic). Single-worker lease assumption documented for WP-3 (ClickHouse leases are not atomic CAS). Non-blocking env note flagged: `POLYGON_RPC_URL`/`POLYMARKET_SUBGRAPH_URL` unset → resolution cascade partial (out of scope).

## Acceptance Gates
1. **Idempotency.** Running the consumer twice does not double-scan the same leased row; lease semantics prevent duplicate work.
2. **No scheduler here.** Consumer runs on explicit invocation; cadence is WP-3.
3. **Offline tests.** Consumer logic tested with a mocked scan callable; no live API calls in CI.
4. **maker/taker scope guard.** No on-chain/Alchemy/log-fetching code added.
5. **Regression.** Existing `tests/test_wallet_discovery*.py` pass with 0 new failures.

## Non-Goals
No scheduler/cadence (WP-3); no on-chain maker/taker enrichment; no Alchemy; no changes to scan API auth; no watchlist tier logic (WP-4); no supersede behavior (WP-2).

## Dependencies
None new. Foundation for WP-2/3/4.

## Cross-References
- [[claude-memory/work-packets/work-packet-wallet-ingestion-v1-sprint]]
- [[claude-memory/session-notes/2026-05-29-wallet-ingestion-audit-results]]

## Connections
- [[claude-memory/work-packets/_index]]
- [[index|Vault Home]]
