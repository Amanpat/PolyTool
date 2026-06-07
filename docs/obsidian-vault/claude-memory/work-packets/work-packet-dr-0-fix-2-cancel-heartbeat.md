---
title: "Work Packet — DR-0-FIX-2 Per-Request Cancel + Heartbeat Supervision"
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
# Work Packet — DR-0-FIX-2 Per-Request Cancel + Heartbeat Supervision

**Status: DRAFT — pending architect review.** Second fix pass. Closes the 2 BLOCKING items from the DR-0-FIX re-review: repo `docs/dev_logs/2026-06-04_dr-0-fix-codex-rereview.md`. Builds on [[claude-memory/work-packets/work-packet-dr-0-fix-shutdown-lock]].

## Goal
Close the two reborn blockers so the scheduler is genuinely safe to start/stop unattended: stop latency is bounded to one in-flight request (not one whole wallet), and a live lock-holder can never be reclaimed because its heartbeat can't die silently.

## Why (re-review findings — the spec)
- **BLOCKING 1 — one wallet can exceed the 60s grace.** `should_stop` is checked only between wallets; one failing endpoint is `4×15+7 = 67s` of retries/backoff (`packages/polymarket/discovery/scan_worker.py:180`, `tools/cli/scan.py:302`, `docker-compose.yml:175`). A SIGTERM mid-wallet → SIGKILL — the original blocker reborn at request granularity.
- **BLOCKING 2 — heartbeat thread unsupervised.** If the daemon heartbeat thread dies while the main drainer lives, mtime goes stale and another worker reclaims a live holder after ~180s (`packages/polymarket/discovery/worker_lock.py:224,229,143,314`). Double-drain on a 3-minute fuse.

## Scope
1. **Request-granularity cooperative cancel.** Thread the stop flag into the scan request/retry loop (`tools/cli/scan.py` retry path + the per-wallet scan in `scan_worker.py`) so a stop aborts the in-flight request/retry instead of finishing the whole wallet. Stop latency must be ≤ one in-flight request (≤ the drain timeout), not ≤ one wallet. A partially-scanned wallet must NOT ingest (all-or-nothing already protects this) and gets re-scanned later.
2. **Heartbeat from the main loop, no unsupervised thread.** Refresh the lock heartbeat from the scheduler's main control loop (the `run_scheduler_blocking` wait already wakes every ~60s — refresh there, on the main thread). Remove the separate daemon heartbeat thread, OR if a thread is retained, supervise it so its death aborts the hold (the holder cannot keep draining while its heartbeat is dead). A live holder must provably refresh; the refresher cannot die silently while the holder lives.
3. **Process-level lock test (re-review SHOULD-FIX C).** Add a real two-subprocess contention test for `O_EXCL` acquisition on the shared lock path (not threads-only).
4. **NITs.** Correct the `--force` help text (`tools/cli/discovery.py:151`) to state it overrides only a stale lock; fix the import-removal note in `docs/dev_logs/2026-06-04_dr-0-fix.md:81` (only `time` was removed).
5. **Clock skew (re-review SHOULD-FIX D) — accept + document, do NOT gate.** In the single-host deployment, the scheduler container and any host worker share the host kernel clock, so skew is ~nil. Document the same-host assumption in the lock module; only revisit if a worker ever runs on a separate machine.

## Definition of Done (each closed WITH a real test)
- [ ] **Bounded stop mid-wallet:** real test — start a drain on a wallet whose endpoint hangs/retries, send the stop, assert the worker aborts within ~one request timeout (not 67s) and the partial wallet is not ingested.
- [ ] **Heartbeat liveness tied to the holder:** real test — there is no path where the main process lives but the heartbeat goes stale (either no separate thread, or thread death aborts the hold). A live holder is never reclaimable.
- [ ] **Process-level atomicity:** two real subprocesses race acquisition → exactly one wins.
- [ ] `--force` help corrected; dev-log import note corrected; same-host clock assumption documented.
- [ ] Focused suite green; the prior 21 shutdown tests still pass.
- [ ] Dev log written; Codex re-review (pass 3) attached.

## Acceptance Gates
1. **Codex adversarial re-review (pass 3) MANDATORY** before merge — same threat model + verify the two blockers are closed end-to-end in the production scan path, not just in a harness.
2. **Tests exercise the real failure, not mocks.** A stop-latency test that doesn't actually drive a slow/retrying request, or a heartbeat test that doesn't simulate thread death / prove main-loop refresh, does NOT satisfy its item.
3. **No new framework/dependency** — stdlib only.
4. **Denylist untouched**; **DR-2 foreground `wallet-scan` path unaffected.**

## Non-Goals
No grace-period inflation as a substitute for cancellation. No retention/Grafana. No cross-machine lock (single-host assumption stands).

## Dependencies
Builds on DR-0-FIX. Gate for the unattended scheduler. Independent of the DR-2 batch-seed run, which proceeds in parallel.

## Cross-References
- repo `docs/dev_logs/2026-06-04_dr-0-fix-codex-rereview.md` — findings (spec)
- [[claude-memory/work-packets/work-packet-dr-0-fix-shutdown-lock]] — first fix pass
- [[claude-memory/work-packets/work-packet-scan-day-run-sprint]]

## Connections
- [[claude-memory/work-packets/_index]]
- [[index|Vault Home]]
