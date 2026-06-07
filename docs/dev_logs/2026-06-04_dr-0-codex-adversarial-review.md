# DR-0 Codex Adversarial Review - Start/Stop Safety + Concurrency Guard

Date: 2026-06-04
Reviewer: Codex
Scope: read-only adversarial review of DR-0 shutdown safety, queue-drain stop behavior, and worker advisory locking. No code fixes and no commit.

## Verdict

DR-0 is **not safe to rely on** for unattended start/stop yet.

Blocking items to close first:

1. Add a bounded shutdown/cancel path; `shutdown(wait=True)` can wait far past Docker's default stop grace.
2. Fix the advisory lock lifetime/staleness mismatch; a scheduler lock older than 30 minutes is treated as stale even while the scheduler is alive.
3. Make lock acquisition atomic and fail closed if the lock cannot be written.

## Findings

| Severity | File:line | Issue | Why it bites |
| --- | --- | --- | --- |
| BLOCKING | `tools/cli/discovery.py:1064`, `packages/research/scheduling/discovery_scheduler.py:619` | SIGTERM shutdown waits unbounded on in-flight jobs. | `_scheduler_start()` calls `stop_discovery_scheduler(scheduler, wait=True)`, which calls `scheduler.shutdown(wait=wait)` with no outer deadline or cancellation. If `queue_drain` is inside a slow scan/API call, Docker can hit its default stop grace and SIGKILL the process. |
| BLOCKING | `packages/research/scheduling/discovery_scheduler.py:484`, `tools/cli/scan.py:73`, `tools/cli/scan.py:314`, `tools/cli/scan.py:2307` | A bounded queue tick is not bounded to Docker stop grace. | `queue_drain` may run `worker.run(max_items=10)`. The default scan path has a 120s HTTP timeout per request and retries. One endpoint alone can exceed 10s; a multi-endpoint scan can exceed it by minutes. DR-0 has no stop-time budget. |
| BLOCKING | `packages/polymarket/discovery/worker_lock.py:120`, `packages/polymarket/discovery/worker_lock.py:121`, `tools/cli/discovery.py:1007` | Live scheduler lock auto-expires after 30 minutes. | The scheduler acquires one lock for its lifetime, but `_is_stale()` treats any lock older than `stale_seconds` as stale even if the PID is alive. After 30 minutes, a normal manual `run-worker` can reclaim the scheduler's live lock and double-drain the same ClickHouse queue. |
| BLOCKING | `packages/polymarket/discovery/worker_lock.py:146`, `packages/polymarket/discovery/worker_lock.py:164` | Lock acquisition is check-then-write, not atomic. | Two contenders can both read no live lock, both write with `Path.write_text()`, and both return success. This is the exact race the lock is meant to prevent. There is no `O_CREAT|O_EXCL`, `os.open(... O_EXCL ...)`, or equivalent. |
| BLOCKING | `packages/polymarket/discovery/worker_lock.py:168`, `packages/polymarket/discovery/worker_lock.py:176` | Lock failure is fail-open. | If the lock directory/file cannot be written, the code logs a warning and still returns success. With an unwritable or missing shared mount, multiple drainers proceed without a lock. |
| SHOULD-FIX | `tools/cli/discovery.py:154`, `tools/cli/discovery.py:500`, `packages/polymarket/discovery/worker_lock.py:147` | `--force` can stomp a genuinely running scheduler. | The warning is explicit, but the flag still overrides a live lock and starts a second drainer. If the requirement is "two drainers on the same queue must be impossible," this escape hatch violates it. |
| SHOULD-FIX | `packages/polymarket/discovery/worker_lock.py:64`, `packages/polymarket/discovery/worker_lock.py:85` | PID liveness trusts a bare PID. | There is no process identity check (start time, command line, container id). PID reuse or namespace mismatch can make a stale lock look live or an unrelated process look like the holder. On Windows, every positive PID is treated as alive until age expiry. |
| SHOULD-FIX | `docker-compose.yml:168`, `docker-compose.yml:171`, `packages/polymarket/discovery/worker_lock.py:41` | Lock sharing depends on the relative `artifacts` mount and working directory. | The compose scheduler and a host manual worker from repo root do share `./artifacts:/app/artifacts`, so that concern holds only for nonstandard manual CWD/container setups. It is not enforced by config or CLI. |
| SHOULD-FIX | `tools/cli/discovery.py:1007`, `tools/cli/discovery.py:1024`, `tools/cli/discovery.py:1065` | Scheduler lock release is not protected by a broad `finally`. | After lock acquisition, only `ImportError` from scheduler start releases immediately. Other start/runtime exceptions before the clean shutdown path can leak a lock and rely on stale reclaim. |
| SHOULD-FIX | `tools/cli/discovery.py:1064`, `packages/research/scheduling/discovery_scheduler.py:624` | Shutdown failure is ignored and still reported clean. | `stop_discovery_scheduler()` returns `False` on shutdown errors, but `_scheduler_start()` ignores the return value, releases the lock, prints "stopped cleanly", and returns 0. |
| SHOULD-FIX | `tests/test_discovery_shutdown.py:103`, `tests/test_discovery_shutdown.py:120` | Signal test is a pattern test, not a process signal test. | It sets a `threading.Event` directly in a helper loop. It does not run `_scheduler_start()`, register SIGTERM, send SIGTERM to the process, or assert exit code 0 under a live scheduler. |
| SHOULD-FIX | `tests/test_discovery_shutdown.py:145`, `tests/test_discovery_shutdown.py:164`, `tests/test_discovery_shutdown.py:202` | Interrupted-scan tests do not simulate real interruption. | The tests use an in-process callable that raises or direct in-memory lease mutation. They do not kill a process mid-request, do not exercise Docker stop grace, and do not prove persisted ClickHouse lease recovery. |
| SHOULD-FIX | `tests/test_discovery_shutdown.py:233`, `tests/test_discovery_shutdown.py:250`, `tests/test_discovery_shutdown.py:259` | Lock tests are sequential and miss the real races. | They do not run two contenders concurrently, do not test atomic file creation, do not test live-lock age expiry after 30 minutes, and do not test PID reuse or host/container namespace behavior. |

## Concerns That Do Not Hold

- DR-2's `export-leaderboard` subparser is additive in the current file. It is registered at `tools/cli/discovery.py:282` and dispatched separately at `tools/cli/discovery.py:353`; DR-0's `_run_worker()` and `_scheduler_start()` paths remain present at `tools/cli/discovery.py:435` and `tools/cli/discovery.py:955`.
- The main scheduler wait loop is not `Event.wait()` with no timeout. It uses `stop_event.wait(timeout=60)` at `tools/cli/discovery.py:1057`.
- Double SIGTERM does not directly double-call shutdown: the handler at `tools/cli/discovery.py:1040` only prints and sets the event. Shutdown is called once after the loop at `tools/cli/discovery.py:1064`. Repeated prints are possible, but no direct re-entrant shutdown path is present.
- SIGTERM's intended normal path returns 0 at `tools/cli/discovery.py:1067`, assuming shutdown returns.
- For the compose scheduler and a manual host worker run from repo root, the default lock path is shared: `DEFAULT_LOCK_PATH` is `artifacts/discovery/worker.lock` at `packages/polymarket/discovery/worker_lock.py:41`, and compose mounts `./artifacts:/app/artifacts` at `docker-compose.yml:168-171`.
- A just-leased item is not durably leased until the post-run flush. `queue_drain` calls `worker.run(...)` then `queue.flush_to_clickhouse(...)` at `packages/research/scheduling/discovery_scheduler.py:484-485`; a SIGKILL before that flush usually leaves the ClickHouse row in its prior state, often `pending`, not permanently leased. Already-durable expired leases are requeued by `requeue_expired_leases()` at `packages/polymarket/discovery/scan_queue.py:176-199`.
- RIS ingest has a real transaction wrapper for ordinary exceptions: `ingest_dossier_findings()` wraps each wallet in `store.deferred_transaction()` at `packages/research/integration/dossier_extractor.py:532`, and `KnowledgeStore.deferred_transaction()` commits or rolls back at `packages/polymarket/rag/knowledge_store.py:340-365`. That does not remove the shutdown blocker because SIGKILL timing is not tested.

## Test Reality

The focused tests pass, but they mostly test direct helpers and mocked/in-memory paths:

- `test_killed_scan_does_not_advance_lifecycle_and_marks_failed` raises from `_exploding_scan`; it does not deliver SIGTERM/SIGKILL during a real HTTP request.
- `test_expired_lease_requeues_interrupted_item` mutates an in-memory queue row and calls `requeue_expired_leases()` directly; it does not persist a leased row to ClickHouse, kill a process, then verify a later worker requeues it.
- Worker-lock tests use one process and sequential calls. They would pass while the non-atomic check/write race and the 30-minute live-lock expiry are still present.
- Scheduler tests use `_FakeScheduler`; they do not run APScheduler with a long-running job and do not measure Docker stop grace.

## Commands Run

```text
git status --short
=> Exit 0. Worktree already dirty before this review, including DR-0/DR-2 files under review and many untracked dev logs/new modules. No existing changes were reverted or overwritten.
```

```text
git log --oneline -5
=> Exit 0
a2ea5be docs(vault): sync Hermes retirement + Discord notification/bot system
2d16394 docs(vera): Phase B live-verified - approve+deny end-to-end through the gate
c66f375 feat(vera): make /pending cards public (operator-requested), keep author-guard
88e2205 docs(vera): Phase B approve/deny - dev log, feature doc, INDEX, CURRENT_DEVELOPMENT
02120ae fix(vera): make approve/deny reservation fail-safe (Codex re-review)
```

```text
python -m polytool --help
=> Exit 0. CLI loaded and printed command help.
```

```text
python -m polytool discovery --help
=> Exit 0. `export-leaderboard` is listed as a discovery subcommand.
```

```text
python -m pytest tests/test_discovery_shutdown.py -q --tb=short
=> 14 passed, 0 failed, 0 skipped in 0.43s
```

```text
python -m pytest tests/test_discovery_scheduler.py -q --tb=short
=> 39 passed, 0 failed, 0 skipped in 0.41s
```

## Files Changed

- `docs/dev_logs/2026-06-04_dr-0-codex-adversarial-review.md` - this read-only review report requested by the operator.

No code files were changed. No commit was made.

## Decisions

- Treated the existing dirty worktree as the review target because the operator explicitly said DR-0 and DR-2 modified the relevant files and asked to verify current on-disk state.
- Classified lock races and unbounded shutdown as blocking because they directly violate the threat model: no double drainer and no stop past Docker grace.
- Did not mark the shared-lock-path concern as a finding for the normal compose + repo-root manual flow because the compose bind mount makes that path shared.

## Open Questions / Blockers

- A live Docker stop timing test is still required after fixes: start `discovery-scheduler`, force or mock a slow queue-drain scan, send `docker compose stop discovery-scheduler`, and assert bounded exit inside the configured grace.
- Decide whether `--force` is allowed to exist at all under the "two drainers impossible" requirement. If it remains, it needs stronger operator gating than a normal boolean flag.

## Codex Review Summary

Tier: Recommended review surface, adversarial stance. Findings: 5 blocking, 8 should-fix, 0 nit. No fixes addressed in this session by request.
