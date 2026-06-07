# DR-0 Start/Stop Safety — Verify + Patch

Date: 2026-06-04
Packet: `docs/obsidian-vault/claude-memory/work-packets/work-packet-dr-0-start-stop-safety.md`
Scope: make starting/stopping the wallet-discovery scanner safe and clean. Research-side only; denylist (kill switch / signing / execution / risk-manager / live bot) untouched.

Codex review status: **RECOMMENDED — adversarial pass advised.** The graceful-shutdown handler is lifecycle-touching (signal trap + APScheduler shutdown + advisory lock around the scheduler entry point). It is NOT in any denylisted execution/signing/risk file, but it changes process-lifecycle behavior, so a Codex adversarial review of `tools/cli/discovery.py` (`_scheduler_start`) and `packages/polymarket/discovery/worker_lock.py` is recommended before commit.

---

## DoD 1 — ClickHouse persistence verified

**Status: DONE (verified; no change needed).**

The ClickHouse service already maps its data dir to a **named Docker volume** that survives `docker compose stop`, `docker compose start`, and `docker compose down` (a `down` WITHOUT `-v` never removes named volumes).

Evidence — `docker-compose.yml` ClickHouse service (lines 2-22):

```yaml
  clickhouse:
    image: clickhouse/clickhouse-server:latest
    container_name: polytool-clickhouse
    ...
    volumes:
      - clickhouse_data:/var/lib/clickhouse
      - ./infra/clickhouse/initdb:/docker-entrypoint-initdb.d:ro
```

Evidence — top-level `volumes:` block declaring the named volume (lines 358-361):

```yaml
volumes:
  clickhouse_data:
  grafana_data:
  n8n_data:
```

`/var/lib/clickhouse` is ClickHouse's entire data directory (tables, parts, metadata, system tables). It is backed by the managed named volume `clickhouse_data`. Docker named volumes are preserved across `stop`/`start` and across `down` (only `down -v` / `docker volume rm` deletes them).

**`-v` is forbidden** for the day-run toggle (DR-1) and any teardown: `docker compose down -v` (or `docker volume rm polytool_clickhouse_data`) is the ONLY supported command that destroys ClickHouse data. Operators and the DR-1 toggle must use `docker compose stop` / `docker compose start` (or plain `down`) — never `down -v`. No teardown was added by this packet.

Note: Grafana (`grafana_data`) and n8n (`n8n_data`) follow the same persistent-named-volume pattern. Per the audit, host-mounted `./kb` (RAG SQLite) and `./artifacts` (raw dossiers) are bind-mounted on the discovery-scheduler service and persist on the host filesystem independently of the container lifecycle.

---

## DoD 2 — Graceful SIGTERM/SIGINT shutdown handler

**Status: DONE (deterministic test evidence; live `docker stop` timing BLOCKED — no Docker in this environment).**

Replaced the naive `while True: time.sleep(60)` wait in `tools/cli/discovery.py::_scheduler_start()` with a `signal` + `threading.Event` signal-aware wait, and added a clean-shutdown helper `stop_discovery_scheduler(scheduler, wait=True)` in `packages/research/scheduling/discovery_scheduler.py` that reuses APScheduler's own `scheduler.shutdown(wait=True)`.

Behavior on SIGTERM (docker stop) / SIGINT (Ctrl-C):
- (a) **stop accepting new jobs** — `scheduler.shutdown(wait=True)` halts job firing.
- (b) **let the in-flight bounded drain tick finish** — `wait=True` blocks until the currently-running `queue_drain` tick (a single bounded `ScanWorker.run`) returns. That tick's final step is `queue.flush_to_clickhouse(...)`, so the lease/queue state is flushed as part of the normal tick completion.
- (c) **flush queue state to ClickHouse** — via the existing flush at the end of `_job_run_queue_drain` (reused, not re-implemented).
- (d) **`scheduler.shutdown(wait=True)` then exit 0** — the handler sets a `threading.Event`; the wait loop unblocks; we call `stop_discovery_scheduler`, release the advisory lock, print "stopped cleanly", and return 0.

Only stdlib `signal` + `threading` + existing APScheduler shutdown were used — **no new dependency / framework** (DR-0 gate 3).

Evidence — test output (`tests/test_discovery_shutdown.py`):

```text
TestStopDiscoveryScheduler::test_shutdown_called_with_wait_true   PASSED
TestStopDiscoveryScheduler::test_falls_back_to_no_arg_shutdown    PASSED
TestStopDiscoveryScheduler::test_never_raises_on_shutdown_error   PASSED
TestStopDiscoveryScheduler::test_none_scheduler_is_safe           PASSED
TestSignalAwareWait::test_event_unblocks_wait_loop                PASSED
```

`test_shutdown_called_with_wait_true` asserts `shutdown(wait=True)` is invoked exactly once. `test_never_raises_on_shutdown_error` proves the helper swallows shutdown errors so a signal handler can always proceed to exit. `test_event_unblocks_wait_loop` proves a simulated SIGTERM (`event.set()`) unblocks the same wait pattern used by `_scheduler_start` (no busy-sleep).

**BLOCKED sub-item:** real `docker stop` exit-within-grace-window timing was NOT measured — Docker/ClickHouse are unavailable in this environment. The deterministic tests simulate the signal and assert the clean-shutdown call chain. Live confirmation (`time docker compose stop discovery-scheduler` completing inside the default 10s grace) should be run by the operator on a host with the stack up.

CLI smoke (still imports + dry-run schedule prints):

```text
$ python -m polytool --help            -> CLI_OK
$ python -m polytool discovery scheduler start --dry-run
Discovery Scheduler -- Dry-run mode (no scheduler started)
Registered jobs (3):
  discovery_loop_a     every 6h                     cron={'hour': '*/6'}
  watchlist_rescan     daily at 01:00 and 13:00     cron={'hour': '1,13'}
  queue_drain          every 15 minutes             cron={'minute': '*/15'}
```

---

## DoD 3 — Interrupted-scan recovery confirmation

**Status: DONE (deterministic test evidence).**

A scan killed mid-flight: the worker marks the queue item **failed**, does **NOT** advance the watchlist lifecycle (all-or-nothing, DEFECT-2 contract), and the lease **re-queues** to pending once its TTL expires. No half-written RIS state; worst case is an orphan dossier dir on disk (acceptable, no corruption).

Evidence — test output (`tests/test_discovery_shutdown.py::TestInterruptedScanRecovery`):

```text
test_killed_scan_does_not_advance_lifecycle_and_marks_failed  PASSED
test_no_dossier_ingest_on_killed_scan                         PASSED
test_expired_lease_requeues_interrupted_item                  PASSED
```

- `test_killed_scan_does_not_advance_lifecycle_and_marks_failed`: scan callable raises mid-flight → `result.failed == 1`, `result.completed == 0`, the watchlist advancer is **never called** (`advanced == []`), and the queue row ends in terminal `failed` with `attempt_count == 1`.
- `test_no_dossier_ingest_on_killed_scan`: the post-scan RIS extractor is **never reached** when the scan itself dies → no half-written KnowledgeStore state can exist.
- `test_expired_lease_requeues_interrupted_item`: a row leased then abandoned (process died holding the lease, expiry in the past) is reclaimed to `pending` by `requeue_expired_leases()` — `lease_owner` cleared, `attempt_count` incremented, and the item is visible to `get_pending()` again (re-queues, not stuck).

This confirms the audit's claim (DEFECT-2 / commit ae4947d): dossier ingest failure or scan death is FATAL to the item, the watchlist is not advanced on zero-ingest, and expired-lease reclaim handles re-queue.

---

## DoD 4 — Concurrency guard (lightweight advisory lock)

**Status: DONE (deterministic test evidence).**

Added a single-host advisory lock (`packages/polymarket/discovery/worker_lock.py`) so a manual `discovery run-worker` **refuses** to start while the scheduler (the canonical drainer) is active. Rationale: ClickHouse leases are not an atomic compare-and-set; two concurrent drainers can double-grab the same `dedup_key`.

Design (deliberately tiny — stdlib only, no daemon, no distributed lock):
- The scheduler entry point (`_scheduler_start`) acquires the lock as `owner="discovery-scheduler"` for its lifetime and releases it on clean shutdown.
- Manual `run-worker` acquires the lock as `owner=args.owner` before draining; on a live conflict it prints a clear refusal and exits 1. A new `--force` flag overrides (logged, marked UNSAFE) for the operator escape hatch.
- A **stale** lock (recorded PID dead on this host, or older than `stale_seconds=1800`) is reclaimed automatically so a crashed worker cannot wedge the queue. A corrupt lock file is treated as absent (never wedges).
- Release only deletes the lock if the current PID owns it (a forced override never deletes the real holder's file).
- Default lock path `artifacts/discovery/worker.lock` (under gitignored `artifacts/`).

Evidence — test output (`tests/test_discovery_shutdown.py::TestWorkerLock`):

```text
test_second_acquire_refused          PASSED
test_force_overrides_live_lock       PASSED
test_stale_lock_reclaimed_by_age     PASSED
test_stale_lock_reclaimed_by_dead_pid PASSED
test_release_only_when_owned         PASSED
test_corrupt_lock_treated_as_absent  PASSED
```

CLI refusal message (manual worker while scheduler holds the lock):

```text
Error: a discovery drainer is already running.
  discovery worker lock held by owner='discovery-scheduler' pid=... since ... (lock file: artifacts/discovery/worker.lock)
Refusing to start a second drainer (ClickHouse leases are not CAS-safe;
concurrent drains can double-grab a queue item). Stop the scheduler
(`docker compose stop discovery-scheduler`) first, or pass --force to
override (UNSAFE: single-worker only).
```

---

## Test summary (focused subset + new file)

Command:

```text
python -m pytest tests/test_wallet_discovery.py tests/test_wallet_discovery_two_tier.py \
  tests/test_wallet_ingestion_notify.py tests/test_discovery_scheduler.py \
  tests/test_wallet_scan.py tests/test_mvf.py tests/test_ris_dossier_extractor.py \
  tests/test_ris_dossier_supersede.py tests/test_discovery_shutdown.py --tb=short -q
```

Result: **349 passed, 0 failed, 0 skipped** (335 baseline + 14 new). No regressions. CLI `python -m polytool --help` imports cleanly.

---

## Files changed (all uncommitted)

- `tools/cli/discovery.py` — signal-aware shutdown in `_scheduler_start`; advisory-lock acquire/release around scheduler + manual worker; `--force` flag; `_run_worker` split into `_run_worker` (lock wrapper) + `_run_worker_locked` (body); added `signal` + `threading` imports.
- `packages/research/scheduling/discovery_scheduler.py` — new `stop_discovery_scheduler(scheduler, wait=True)` clean-shutdown helper.
- `packages/polymarket/discovery/worker_lock.py` — NEW: single-host advisory lock (acquire/release/stale-reclaim).
- `tests/test_discovery_shutdown.py` — NEW: 14 tests across the four DR-0 concerns.
- `docs/dev_logs/2026-06-04_dr-0-start-stop-safety.md` — this dev log.

## Gates

1. **No data loss path on stop** — DONE: graceful shutdown waits for the in-flight drain tick (which flushes to ClickHouse); interrupted scans fail cleanly and re-queue via expired-lease reclaim; ClickHouse data on a persistent named volume.
2. **`-v` stays forbidden** — DONE: documented above; no teardown added.
3. **No new framework** — DONE: stdlib `signal` + `threading` + existing APScheduler shutdown only.
4. **Denylist untouched** — DONE: no execution / kill-switch / signing / risk-manager files touched.

## Open items / blockers

- Live `docker stop` exit-within-grace-window timing is **BLOCKED** (no Docker in this environment) — operator should confirm on a host with the stack running.
- Codex adversarial review recommended on the lifecycle-touching shutdown path before commit.
