---
title: "Work Packet — DR-0 Start/Stop Safety (Verify + Patch)"
type: work_packet
status: active
source_zone: claude_memory
last_updated: 2026-06-04
lifecycle: draft
tags: [work-packet, wallet-discovery, day-run, scheduler, safety, shutdown]
target_agent: claude-code
acceptance_criteria:
  - See Definition of Done
---
# Work Packet — DR-0 Start/Stop Safety (Verify + Patch)

**Status: DRAFT — pending architect review.**

## Goal
Make starting and stopping the scanner safe and clean, so the operator can toggle scans on/off without losing or corrupting data. Verify what's already protective; patch the gaps.

## Context (audit evidence)
- Scheduler is a blocking process: `while True: time.sleep(60)` in `tools/cli/discovery.py:814-833`; APScheduler `BackgroundScheduler` via `start_discovery_scheduler()` (`packages/research/scheduling/discovery_scheduler.py:549-595`).
- Drain bound `max_items=10`, `lease_seconds=300` (`config/discovery_scheduler.json:27-33`).
- All-or-nothing per-wallet ingest is already in place (6/1 fix, commit ae4947d): worker marks the queue item failed and does NOT advance lifecycle on zero-ingest.
- Host-mounted persistence confirmed for `./kb` (RAG SQLite) and `./artifacts` (raw dossiers) in the `discovery-scheduler` service (`docker-compose.yml:159-176`). **ClickHouse's own volume was NOT shown in the audit → must verify.**
- No SIGTERM/SIGINT handler was found (the naive sleep loop) → `docker stop` hard-kills an in-flight scan.

## Scope
1. **Verify ClickHouse persistence.** Inspect the ClickHouse compose service: does its data dir map to a named or host volume that survives `docker compose stop` and `docker compose down` (without `-v`)? If NOT, add a persistent volume. Document the result.
2. **Graceful shutdown handler.** Add SIGTERM/SIGINT handling to the discovery scheduler entry point so a stop: (a) stops accepting new jobs, (b) lets an in-flight bounded drain tick finish OR aborts it cleanly releasing the lease, (c) flushes queue state to ClickHouse, (d) exits 0 within Docker's stop grace period. Replace the naive `while True: sleep` wait with a signal-aware wait.
3. **Interrupted-scan recovery confirmation.** Confirm (with a test) that a scan killed mid-flight: leaves no half-written RIS state (all-or-nothing holds), releases/expires its lease so the item re-queues, and at worst leaves an orphan dossier run dir on disk (no corruption).
4. **Concurrency guard (lightweight).** Document/enforce that a manual `run-worker` must not run while the scheduler is active (lease atomicity is not CAS-safe). A simple advisory lock or a clear refusal/warning is acceptable; do not over-engineer.

## Steps
1. Inspect + (if needed) fix the ClickHouse volume in `docker-compose.yml`; record findings in the dev log.
2. Add the signal handler + signal-aware wait to the scheduler entry point.
3. Write tests: SIGTERM mid-tick → clean exit, queue flushed, lease released, no lifecycle advance on the interrupted item.
4. Add the concurrency advisory (lock or refusal) for manual worker vs scheduler.
5. Dev log + update CURRENT_STATE.

## Definition of Done
- [ ] ClickHouse persistence verified (or fixed): `stop`/`start` and `down` (no `-v`) preserve all ClickHouse data; documented.
- [ ] Scheduler traps SIGTERM/SIGINT, finishes/aborts the current tick cleanly, flushes queue, exits 0 within the stop grace window.
- [ ] Test proves an interrupted scan re-queues via lease and leaves RIS uncorrupted (all-or-nothing).
- [ ] Manual-worker-vs-scheduler concurrency is guarded or clearly refused.
- [ ] Dev log written; CURRENT_STATE updated.

## Acceptance Gates
1. **No data loss path on stop.** A stop mid-scan must never leave half-written RIS state or a permanently-stuck queue item.
2. **`-v` stays forbidden.** Document it; the toggle (DR-1) must never call it.
3. **No new framework.** Use stdlib `signal` + the existing APScheduler shutdown; no new dependency.
4. **Denylist untouched.** No execution/kill-switch/signing/risk-manager files.

## Non-Goals
No retention/prune logic (separate fast-follow); no orphan-folder auto-sweep (nice-to-have, defer); no change to the all-or-nothing ingest contract.

## Dependencies
None. Gate for DR-1 and any unattended scheduler run.

## Cross-References
- [[claude-memory/work-packets/work-packet-scan-day-run-sprint]]
- [[claude-memory/session-notes/2026-06-04-scan-day-run-readiness-scoping]]

## Connections
- [[claude-memory/work-packets/_index]]
- [[index|Vault Home]]
