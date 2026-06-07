# DR-0-FIX-2 Codex adversarial re-review pass 3

Date: 2026-06-04

Scope: read-only adversarial re-review of DR-0-FIX-2 cancel + heartbeat paths. No production code was changed. This file is the only write.

## Findings

| Severity | file:line | Issue | Why |
|---|---|---|---|
| BLOCKING | `packages/polymarket/discovery/scan_worker.py:70`, `tools/cli/scan.py:103`, `tools/cli/scan.py:1476`, `tools/cli/scan.py:1498`, `tools/cli/scan.py:1217`, `packages/polymarket/http_client.py:91`, `packages/polymarket/http_client.py:108` | Request-granularity cancel does not cover the full production scheduler scan path. | The scheduler drain uses the default/lite scan path, and that path enables `compute_clv`. After the cancel-aware `post_json` calls, `run_scan()` enters CLV preflight/enrichment. CLV builds `ClobClient`, whose `HttpClient` has its own retry loop and blocking `time.sleep(delay)` with no `_raise_if_cancelled()` check. One CLOB timeout path can run `6 * 20s` requests plus exponential sleeps before returning; per-position CLV can do multiple such calls. A SIGTERM during this phase is not bounded by the new `scan.py` cancel hook. |
| BLOCKING | `tools/cli/discovery.py:586`, `packages/polymarket/discovery/scan_worker.py:259`, `packages/polymarket/discovery/scan_worker.py:298`, `packages/polymarket/discovery/worker_lock.py:74`, `packages/polymarket/discovery/worker_lock.py:173`, `tools/cli/scan.py:2040`, `tools/cli/scan.py:2381`, `tools/cli/scan.py:378`, `tools/cli/scan.py:391` | Manual worker lock can go heartbeat-stale while it is actively scanning one wallet. | Manual `run-worker` passes `heartbeat=lock.beat` but no `should_stop`; `ScanWorker` beats only between wallets, then calls the full scan. The default lock threshold is `3 * 60s = 180s`. The manual path does not set the scheduler-only `SCAN_HTTP_TIMEOUT_SECONDS=15`, so `scan.py` defaults to 120s per request. One failing endpoint can take `4 * 120s + 1+2+4s = 487s`, already above 180s; even with 15s requests, three retrying endpoints can exceed 180s. A scheduler/manual drainer can then reclaim the stale-looking live lock and overlap the active manual scan. |
| BLOCKING | `tools/cli/discovery.py:1076`, `tools/cli/discovery.py:1088`, `packages/research/scheduling/discovery_scheduler.py:698`, `packages/research/scheduling/discovery_scheduler.py:760`, `packages/research/scheduling/discovery_scheduler.py:529`, `packages/research/scheduling/discovery_scheduler.py:533` | Scheduler stop can release the worker lock before the in-flight drain job has finished. | The CLI calls `run_scheduler_blocking(..., shutdown_wait=False, heartbeat=lock.beat)` and unconditionally releases the lock in `finally` when that returns. The scheduler code documents that `wait=False` does not wait for the queue; the queue job itself is still `worker.run(...)` followed by `queue.flush_to_clickhouse(...)`. If a job thread is still returning from an in-flight scan/cancel/flush, the lock file can disappear while the drainer is still active, allowing another drainer to acquire it. |
| SHOULD-FIX | `tests/test_discovery_shutdown.py:486`, `tests/test_discovery_shutdown.py:497`, `tests/test_discovery_shutdown.py:649`, `tests/support/sched_sigterm_harness.py:103` | Tests pass but miss the production-risk cases above. | The manual heartbeat test uses an instant fake scan, so it only proves beats between short wallets, not during a long wallet. The request-granularity test drives `scan_mod.get_json()` directly, not the default wallet scan with CLV. The SIGTERM harness has no `WorkerLock`, so it cannot catch lock release before job completion. |

## Cleared checks

- The old daemon heartbeat thread is gone. `WorkerLock` only exposes `beat()` and `release()`; acquisition starts no background thread (`packages/polymarket/discovery/worker_lock.py:203`, `packages/polymarket/discovery/worker_lock.py:236`).
- Scheduler main-loop heartbeat exists and is live while `run_scheduler_blocking()` is polling: `_beat()` is called immediately and on each wait-loop poll (`packages/research/scheduling/discovery_scheduler.py:742`, `packages/research/scheduling/discovery_scheduler.py:747`, `packages/research/scheduling/discovery_scheduler.py:755`). Because APScheduler jobs run off the blocking main loop, this concern does not hold for a normal long scheduler tick before shutdown.
- The module cancel hook is process-global, but it is installed only when `ScanWorker.run(should_stop=...)` is used and is cleared in a `finally` (`tools/cli/scan.py:325`, `packages/polymarket/discovery/scan_worker.py:216`, `packages/polymarket/discovery/scan_worker.py:231`). I found no stale-hook leak in the reviewed drain paths.
- `ScanCancelled` from the cancel-aware `scan.py` retry/backoff path is not swallowed by `scan.py` itself. `ScanWorker` catches it before the broad `except Exception`, releases the lease to pending, does not ingest, does not complete, and does not increment attempts (`packages/polymarket/discovery/scan_worker.py:326`, `packages/polymarket/discovery/scan_worker.py:332`, `packages/polymarket/discovery/scan_queue.py:155`, `packages/polymarket/discovery/scan_queue.py:171`).
- `release()` versus `requeue_expired_leases()` does not create a double-enqueue in the single-drainer in-memory manager: `release()` only mutates a currently leased row to pending with no attempt increment, while `requeue_expired_leases()` is a separate scan over currently leased expired rows (`packages/polymarket/discovery/scan_queue.py:155`, `packages/polymarket/discovery/scan_queue.py:199`). This only remains true while the worker lock invariant holds.
- `_cancellable_sleep()` is bounded and not a busy spin: it checks cancel, computes remaining time, returns at deadline, and sleeps at most 0.2s per slice (`tools/cli/scan.py:355`).

## Verdict

Both original blockers are not closed in the production path: the daemon-thread heartbeat issue is fixed for the scheduler main loop, but request-granularity cancel is incomplete for the CLV production path, and Part 3 surfaces new BLOCKING lock-staleness/lock-release issues; DR-0 is not safe for unattended start/stop.

## Commands run

`git status --short`

Output: dirty worktree with candidate DR-0/DR-1/DR-2/DR-3 changes already present; no reviewed code was modified by this pass.

`git log --oneline -5`

Output:

```text
a2ea5be docs(vault): sync Hermes retirement + Discord notification/bot system
2d16394 docs(vera): Phase B live-verified - approve+deny end-to-end through the gate
c66f375 feat(vera): make /pending cards public (operator-requested), keep author-guard
88e2205 docs(vera): Phase B approve/deny - dev log, feature doc, INDEX, CURRENT_DEVELOPMENT
02120ae fix(vera): make approve/deny reservation fail-safe (Codex re-review)
```

`python -m polytool --help`

Output: exit 0; CLI loaded and printed the PolyTool command list.

`pytest -q tests/test_discovery_shutdown.py --tb=short`

Output:

```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.2, pluggy-1.6.0
rootdir: D:\Coding Projects\Polymarket\PolyTool
configfile: pyproject.toml
plugins: anyio-4.12.0
collected 28 items

tests\test_discovery_shutdown.py ............................            [100%]

============================= 28 passed in 9.93s ==============================
```

## Files changed

- `docs/dev_logs/2026-06-04_dr-0-fix-2-codex-rereview.md` - added this read-only review digest and command record.

## Open questions

- None for the review. The blockers above require implementation work before DR-0 can be treated as unattended start/stop safe.
