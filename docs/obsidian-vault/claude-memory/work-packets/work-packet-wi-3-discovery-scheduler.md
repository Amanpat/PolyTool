---
title: "Work Packet — WI-3 Discovery + Rescan Scheduler"
type: work_packet
status: active
source_zone: claude_memory
last_updated: 2026-05-29
lifecycle: draft
tags: [work-packet, wallet-discovery, ingestion, scheduler]
target_agent: claude-code
acceptance_criteria:
  - See Definition of Done
---
# Work Packet — WI-3 Discovery + Rescan Scheduler

**Status: DRAFT — pending architect review.**

## Goal
Run discovery, queue drain, and watchlist rescans on a cadence by **reusing the existing RIS APScheduler pattern** (not a second scheduler framework). Add tier-aware skip-if-recent so wallets aren't re-enqueued within their freshness threshold, and prioritize the scan queue: locked watchlist → candidate watchlist → newly-discovered → rest.

## Context (audit evidence)
- No discovery scheduler exists; `tools/cli/discovery.py` is manual-invoke only.
- No staleness/rescan constant exists anywhere (the "14-day default" is fiction) — this logic is greenfield.
- Reuse target: `packages/research/scheduling/scheduler.py :: JOB_REGISTRY` (lines 54-103), `start_research_scheduler` (lines 314-410); docker pattern in `docker-compose.yml :: ris-scheduler` (lines 132-176).
- Priority field exists on `scan_queue` DDL (`infra/clickhouse/initdb/27_wallet_discovery.sql`).

## Scope
1. **Scheduler jobs** (reusing the APScheduler registry pattern): discovery (`run-loop-a`) on a cadence; watchlist-rescan (enqueue watchlist members by tier); queue-drain worker (note: the WP-1 worker may run as a long-lived service rather than a cron tick — choose whichever fits the existing service model and document it).
2. **Tier-aware skip-if-recent.** Before enqueueing a wallet, compare its `last_scan` timestamp against a per-tier threshold; skip if within window. Defaults (config, not hardcoded): locked watchlist ~6h, candidate watchlist ~24h, discovered ~14d. Use the watchlist/queue manifest for the comparison.
3. **Scan-order priority.** Set `scan_queue.priority` so the consumer drains locked watchlist first, then candidate watchlist, then newly-discovered, then the rest.
4. **Config knobs.** All cadences + thresholds in a config file/section, operator-tunable without code change.
5. **Service definition.** Add a compose service mirroring the `ris-scheduler` pattern (`restart: unless-stopped`).

## Steps
1. Register discovery + rescan jobs in the existing scheduler pattern.
2. Implement tier-aware skip-if-recent against last_scan timestamps.
3. Wire scan-queue priority by tier/source.
4. Externalize cadences + thresholds to config.
5. Add the compose service.
6. Tests (skip-if-recent, priority ordering) + dev log.

## Definition of Done
- [x] Scheduler starts and runs discovery on cadence, enqueues rescans by tier, worker drains. — `DISCOVERY_JOB_REGISTRY` (discovery_loop_a / watchlist_rescan / queue_drain) in `packages/research/scheduling/discovery_scheduler.py`; `discovery scheduler {status,start,run-job}` CLI.
- [x] A wallet within its tier's freshness window is NOT re-enqueued (skip-if-recent). — vs watchlist `last_scanned_at` (FINAL); tested.
- [x] Queue drains in priority order: locked → candidate → discovered → rest. — tier→priority (1/2/3/4); worker already sorts `(priority, created_at)`; tested.
- [x] Cadences/thresholds are config-driven. — `config/discovery_scheduler.json` (loaded defensively).
- [x] Compose service added; dev log written. — `discovery-scheduler` service (`restart: unless-stopped`).

**COMPLETED 2026-06-01.** 82 passed (39 new + 43 RIS unaffected); broader 273 passed. Reuses RIS APScheduler `JOB_REGISTRY` pattern (gate 1). Single-tick bounded drain per fire (WI-1 single-worker safety — ClickHouse leases not atomic CAS). Forward-compatible `resolve_tier` reads WI-4 `tier`/`locked` cols if present else falls back to `lifecycle_state`/`source` — **no watchlist DDL changed** (WI-4 owns it; full locked/candidate tiering activates when WI-4 lands). WP-2 supersede precondition is MERGED. Offline-only (no live scheduler runtime per packet).

## Acceptance Gates
1. **Reuse, don't reinvent.** Uses the existing APScheduler `JOB_REGISTRY` pattern; no second scheduler framework introduced.
2. **No RIS regression.** Existing RIS scheduler jobs/tests unaffected.
3. **Supersede precondition.** Frequent rescan cadence assumes WP-2 is merged (call this out; do not enable sub-daily rescans without it).
4. **No real-time.** No Alchemy/WebSocket live monitoring (that is deferred Loop B).

## Non-Goals
No n8n (later phase); no real-time/Alchemy; no modification of existing RIS scheduler jobs; thresholds are config, not constants.

## Dependencies
WP-1 (consumer to schedule) + WP-2 (supersede before frequent rescans).

## Cross-References
- [[claude-memory/work-packets/work-packet-wallet-ingestion-v1-sprint]]
- [[claude-memory/session-notes/2026-05-29-wallet-ingestion-audit-results]]

## Connections
- [[claude-memory/work-packets/_index]]
- [[index|Vault Home]]
