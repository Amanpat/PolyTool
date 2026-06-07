---
title: "Work Packet — DR-0-FIX Shutdown Grace + Worker Lock Hardening"
type: work_packet
status: active
source_zone: claude_memory
last_updated: 2026-06-04
lifecycle: draft
tags: [work-packet, wallet-discovery, day-run, scheduler, shutdown, lock, fix, codex]
target_agent: claude-code
acceptance_criteria:
  - See Definition of Done
---
# Work Packet — DR-0-FIX Shutdown Grace + Worker Lock Hardening

**Status: DRAFT — pending architect review.** Supersedes the BLOCKED items in [[claude-memory/work-packets/work-packet-dr-0-start-stop-safety]]. Grounded in the Codex adversarial review: repo `docs/dev_logs/2026-06-04_dr-0-codex-adversarial-review.md` (5 BLOCKING, 8 SHOULD-FIX).

## Goal
Make the discovery scheduler genuinely safe to start/stop unattended: a SIGTERM always exits within the Docker stop grace with no half-written RIS and no stuck lease, and two drainers on one queue are truly impossible. Fix the five blockers + the safety-relevant should-fixes, and replace the test-theater with tests that exercise the real failures.

## Why (Codex findings — these are the spec)
Five BLOCKING defects, all in the scheduler/lock path (none in the foreground `wallet-scan` batch path):
1. **Unbounded shutdown** — `stop_discovery_scheduler(wait=True)` → `scheduler.shutdown(wait=True)` with no deadline (`tools/cli/discovery.py:1064`, `packages/research/scheduling/discovery_scheduler.py:619`). A mid-scan drain can blow past Docker grace → SIGKILL.
2. **Tick not bounded to grace** — `queue_drain` runs `worker.run(max_items=10)`; default scan HTTP timeout is 120s/request with retries (`discovery_scheduler.py:484`, `tools/cli/scan.py:73,314,2307`). One tick can run minutes.
3. **Live lock expires at 30m** — `_is_stale()` treats any lock older than `stale_seconds` as stale even with a live PID (`packages/polymarket/discovery/worker_lock.py:120-121`). After 30m a manual worker reclaims the live scheduler's lock → double-drain.
4. **Non-atomic lock** — check-then-`write_text()`, no `O_EXCL` (`worker_lock.py:146,164`). Two contenders both acquire.
5. **Fail-open lock** — unwritable lock → warn + return success (`worker_lock.py:168,176`). Drainers run unlocked.

## Scope
1. **Bounded, cooperative shutdown.**
   - On SIGTERM/SIGINT set the existing stop event; have `ScanWorker.run()` check it BETWEEN wallets and return promptly (cooperative cancel — do not start a new wallet once stopping).
   - `stop_discovery_scheduler(wait=False)` (or `wait=True` with a bounded join) so shutdown never blocks unbounded; any wallet truly in-flight is abandoned safely (lease expiry + per-wallet all-or-nothing protect data).
   - Give the drain scan path a stop-time budget: a per-request timeout well under the grace window (drain-scoped, not the global 120s).
   - Raise the compose `stop_grace_period` for `discovery-scheduler` (e.g. 30–60s) to give a clean cooperative stop room.
   - Invariant: from SIGTERM, the process exits within the grace window every time, RIS uncorrupted, no permanently-leased item.
2. **Lock: liveness-based staleness via heartbeat.**
   - Holder refreshes a heartbeat (mtime touch / heartbeat ts) on an interval (~60s). Stale = no heartbeat within threshold (e.g. 3× interval). A live scheduler refreshing its heartbeat NEVER looks stale. This also retires reliance on bare-PID liveness (the Windows/PID-reuse should-fix).
3. **Atomic acquisition + fail-closed.**
   - Acquire via `os.open(path, O_CREAT|O_EXCL|O_WRONLY)`. If it exists → contention path: reclaim ONLY if heartbeat-stale.
   - If the lock cannot be created/written for any reason other than "held by a live holder," REFUSE to run (non-zero exit). No unlocked drain, ever.
4. **`--force` cannot stomp a live holder.**
   - `--force` overrides only a heartbeat-stale lock; against a live heartbeat it refuses (or no-ops). Keeps a recovery hatch without reintroducing double-drain.
5. **Cheap correctness should-fixes.**
   - Wrap acquire → run → shutdown in a broad `try/finally` so any exception releases the lock (`discovery.py:1007,1024,1065`).
   - Propagate `stop_discovery_scheduler()`'s `False` return: non-zero exit, and do NOT print "stopped cleanly" unless it was (`discovery.py:1064`).

## Steps
1. Cooperative stop flag in `ScanWorker.run()` + `shutdown(wait=False)` + drain-scoped request timeout; bump compose `stop_grace_period`.
2. Rewrite `worker_lock.py`: atomic `O_EXCL` create, heartbeat refresh + heartbeat-based staleness, fail-closed, `--force` stale-only.
3. Broad `finally` for lock release; propagate shutdown-failure exit code.
4. Replace the test theater (see DoD tests below).
5. Dev log + update CURRENT_STATE / CURRENT_DEVELOPMENT.
6. Hand to Codex for a mandatory adversarial re-review before merge.

## Definition of Done (each blocker closed WITH a real test)
- [ ] **Bounded shutdown:** subprocess test — start the scheduler entry with a deliberately slow/mocked drain, send SIGTERM, assert exit within a bounded time; exit code reflects clean vs failed shutdown. (Not a `threading.Event` pattern test.)
- [ ] **Cooperative cancel:** worker stops between wallets on the stop flag; in-flight wallet abandoned without RIS corruption (per-wallet transaction holds).
- [ ] **Live lock not reclaimed:** holder with a fresh heartbeat; advance time past the old 30m threshold; a second acquirer is REFUSED.
- [ ] **Atomic acquisition:** two real concurrent contenders (subprocess/thread on the `O_EXCL` primitive) → exactly one wins.
- [ ] **Fail-closed:** unwritable lock path → acquisition refuses, non-zero exit (no unlocked run).
- [ ] **`--force` stale-only:** live heartbeat → `--force` refused/no-op; stale lock → `--force` reclaims.
- [ ] Broad `finally` releases the lock on startup/runtime exceptions; shutdown-failure propagates to a non-zero exit + honest message.
- [ ] Focused suite green; the prior 14 shutdown tests upgraded (not just passing on synthetic paths).
- [ ] Dev log written; Codex re-review attached.

## Acceptance Gates
1. **Codex adversarial re-review is MANDATORY** before merge — this is concurrency + lifecycle code that already shipped 5 blockers once. Re-run the same threat model.
2. **Tests exercise the real failure, not mocks.** Any DoD test that only asserts a mock was called or mutates in-memory state does NOT satisfy that item (this is the exact gap that hid the blockers).
3. **No new framework / dependency.** stdlib `signal`/`os`/`threading` only.
4. **Denylist untouched** — kill switch, signing, order execution, risk manager, live bot.
5. **Foreground batch path unaffected** — `wallet-scan` (DR-2) must not regress; it does not use this lock/scheduler.

## Non-Goals
No retention cap; no Grafana; no real-time monitoring. Live `docker compose stop` timing remains an operator verification step (no Docker in build env) — the subprocess SIGTERM test substitutes for the in-process logic.

## Dependencies
None new. Gate for the unattended scheduler phase. Independent of the DR-2 batch-seed run (which can proceed first).

## Cross-References
- repo `docs/dev_logs/2026-06-04_dr-0-codex-adversarial-review.md` — findings (spec)
- [[claude-memory/work-packets/work-packet-dr-0-start-stop-safety]] — original packet (BLOCKED items superseded here)
- [[claude-memory/work-packets/work-packet-scan-day-run-sprint]]
- [[claude-memory/session-notes/2026-06-04-scan-day-run-readiness-scoping]]

## Connections
- [[claude-memory/work-packets/_index]]
- [[index|Vault Home]]
