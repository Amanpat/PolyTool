# DR-0-FIX Codex Adversarial Re-Review

Date: 2026-06-04
Scope: read-only adversarial re-review of DR-0-FIX shutdown grace and worker lock.
Result: NOT SAFE for unattended start/stop yet.

## Files changed

- `docs/dev_logs/2026-06-04_dr-0-fix-codex-rereview.md` - this report only.

No code was fixed and no commit was made.

## Digest Findings

| Severity | File:line | Issue | Why it bites |
| --- | --- | --- | --- |
| BLOCKING | `packages/polymarket/discovery/scan_worker.py:180`, `packages/polymarket/discovery/scan_worker.py:205`, `packages/polymarket/discovery/scan_worker.py:236`, `tools/cli/scan.py:302`, `tools/cli/scan.py:314`, `tools/cli/scan.py:329`, `tools/cli/scan.py:334`, `docker-compose.yml:175` | SIGTERM is only honored between wallets, but one wallet scan can exceed the 60s Docker stop grace. | `request_timeout_seconds=15` is per HTTP attempt, not per wallet. `post_json()` defaults to 3 retries, which yields 4 attempts plus 1+2+4s backoff: `4*15+7 = 67s` for one failed endpoint. The default lite scan has multiple sequential endpoints, so SIGTERM mid-wallet can still become SIGKILL before the next `should_stop` check. This is the original shutdown blocker reborn. |
| BLOCKING | `packages/polymarket/discovery/worker_lock.py:224`, `packages/polymarket/discovery/worker_lock.py:225`, `packages/polymarket/discovery/worker_lock.py:229`, `packages/polymarket/discovery/worker_lock.py:234`, `packages/polymarket/discovery/worker_lock.py:143`, `packages/polymarket/discovery/worker_lock.py:159`, `packages/polymarket/discovery/worker_lock.py:314`, `packages/polymarket/discovery/worker_lock.py:335` | Lock liveness depends on an unsupervised daemon heartbeat thread. | The main drainer can outlive a stopped heartbeat thread. If the heartbeat thread dies for any unhandled target exception, no code detects it or fail-stops the holder; after about 180s the mtime looks stale and another drainer can reclaim a live holder's lock. Routine `os.utime` `OSError`s are caught, so that specific concern does not kill the thread, but independent daemon-thread death is not supervised. |
| SHOULD-FIX | `tests/test_discovery_shutdown.py:272`, `tests/test_discovery_shutdown.py:276`, `tests/test_discovery_shutdown.py:294`, `tests/test_discovery_shutdown.py:297`, `tests/test_discovery_shutdown.py:19` | Atomicity is tested with 12 threads in one process, not with competing processes or the Docker bind mount. | The real contention is scheduler container vs host/manual worker on `./artifacts:/app/artifacts`. `O_EXCL` is the right primitive on normal local filesystems, but there is no process-level or bind-mount proof for the deployment path. |
| SHOULD-FIX | `packages/polymarket/discovery/worker_lock.py:152`, `packages/polymarket/discovery/worker_lock.py:159`, `packages/polymarket/discovery/worker_lock.py:214` | Staleness is wall-clock and mtime skew sensitive. | A reader compares its `time.time()` to the file mtime. Coarse mtime resolution is probably not a 180s-threshold problem on normal filesystems, but host/container clock skew can make a fresh lock look stale or a stale lock look fresh. |
| NIT | `tools/cli/discovery.py:151` | `--force` help text still says it overrides the advisory lock and runs even if another drainer holds it. | The code no longer does that: `acquire_worker_lock()` refuses a live lock regardless of `force` at `packages/polymarket/discovery/worker_lock.py:315` to `packages/polymarket/discovery/worker_lock.py:318`. The help text is stale and misleading, but the safety concern does not hold in code. |
| NIT | `docs/dev_logs/2026-06-04_dr-0-fix.md:81`, `tools/cli/discovery.py` | Evidence report says `signal`/`threading`/`time` imports were removed; current diff only shows `time` removed. | Grep found no downstream importer of `tools.cli.discovery.signal`, `.threading`, or `.time`, and normal imports use `main` or the module alias without those attributes. No breakage found, but the evidence claim is imprecise. |

## Part 1 - Original 5 Blockers

1. Unbounded shutdown: partly closed, but not end-to-end closed.
   `run_scheduler_blocking()` installs signal handlers at `packages/research/scheduling/discovery_scheduler.py:718` to `packages/research/scheduling/discovery_scheduler.py:726`, sets the drain-stop flag in the handler at `packages/research/scheduling/discovery_scheduler.py:707` to `packages/research/scheduling/discovery_scheduler.py:716`, and calls `stop_discovery_scheduler(..., wait=False)` at `packages/research/scheduling/discovery_scheduler.py:738`. The CLI delegates to it at `tools/cli/discovery.py:1066`. This removes the old unbounded `shutdown(wait=True)` wait, but Part 2A shows the process can still outlive Docker grace while a wallet scan is in flight.

2. Tick not grace-bounded: not genuinely closed.
   The intended bound is `queue_drain.request_timeout_seconds: 15` at `config/discovery_scheduler.json:27` to `config/discovery_scheduler.json:33`, applied through `SCAN_HTTP_TIMEOUT_SECONDS` at `packages/research/scheduling/discovery_scheduler.py:506` to `packages/research/scheduling/discovery_scheduler.py:513`, with compose grace at `docker-compose.yml:175`. That is only a per-attempt timeout. `tools/cli/scan.py:302` to `tools/cli/scan.py:338` makes one failed API stage about 67s, so the tick is not bounded to 60s.

3. Live-lock 30m expiry: closed in the narrow code path.
   Staleness no longer uses `acquired_at`; `LockInfo.acquired_at` is informational at `packages/polymarket/discovery/worker_lock.py:92`, and `_is_stale()` uses mtime age at `packages/polymarket/discovery/worker_lock.py:143` to `packages/polymarket/discovery/worker_lock.py:160`. A live holder refreshes mtime via `beat()` at `packages/polymarket/discovery/worker_lock.py:211` to `packages/polymarket/discovery/worker_lock.py:218`.

4. Non-atomic acquisition: closed in code, not fully proven in deployment.
   `_exclusive_create()` uses `os.open(..., os.O_CREAT | os.O_EXCL | os.O_WRONLY, ...)` at `packages/polymarket/discovery/worker_lock.py:163` to `packages/polymarket/discovery/worker_lock.py:170`, and acquisition goes through that path at `packages/polymarket/discovery/worker_lock.py:305` to `packages/polymarket/discovery/worker_lock.py:312`.

5. Fail-open: closed in code.
   Lock directory creation errors raise `WorkerLockError` at `packages/polymarket/discovery/worker_lock.py:299` to `packages/polymarket/discovery/worker_lock.py:303`; lock create/write errors fail closed at `packages/polymarket/discovery/worker_lock.py:172` to `packages/polymarket/discovery/worker_lock.py:183`. Manual worker and scheduler call sites catch `WorkerLockHeld`/`WorkerLockError` and return 1 at `tools/cli/discovery.py:501` to `tools/cli/discovery.py:523` and `tools/cli/discovery.py:1026` to `tools/cli/discovery.py:1042`.

## Part 2 - New Design Probes

### A. Between-wallet cancel vs grace

BLOCKING.

`ScanWorker.run()` documents and implements stop checks only between wallets: before first work at `packages/polymarket/discovery/scan_worker.py:191` to `packages/polymarket/discovery/scan_worker.py:193`, and before leasing the next wallet at `packages/polymarket/discovery/scan_worker.py:205` to `packages/polymarket/discovery/scan_worker.py:215`. The scan starts at `packages/polymarket/discovery/scan_worker.py:236`; no mid-wallet cancellation is passed through.

Worst-case math:

- Scheduler sets `SCAN_HTTP_TIMEOUT_SECONDS=15` via `packages/research/scheduling/discovery_scheduler.py:511` to `packages/research/scheduling/discovery_scheduler.py:513`.
- `post_json()` default is `retries=3` at `tools/cli/scan.py:329` to `tools/cli/scan.py:335`.
- The retry loop attempts while `attempt <= retries`: first request plus 3 retries. On each of the first three failures it sleeps 1, 2, and 4 seconds at `tools/cli/scan.py:318` to `tools/cli/scan.py:325`.
- One failed endpoint can therefore take `4 * 15 + (1 + 2 + 4) = 67s`, already above `discovery-scheduler.stop_grace_period: 60s` at `docker-compose.yml:175`.

The default lite profile includes `ingest_positions`, `compute_pnl`, `enrich_resolutions`, and `compute_clv` at `tools/cli/scan.py:103` to `tools/cli/scan.py:109`. `run_scan()` then makes sequential API calls including positions, resolve, trades, detectors, pnl, enrich resolutions, and dossier export at `tools/cli/scan.py:2339` to `tools/cli/scan.py:2418`. CLV also constructs a CLOB client without the drain-scoped 15s timeout at `tools/cli/scan.py:1144` to `tools/cli/scan.py:1152`; `ClobClient` defaults to 20s at `packages/polymarket/clob.py:87` to `packages/polymarket/clob.py:93`.

### B. Heartbeat-thread death

BLOCKING.

The heartbeat is a daemon thread at `packages/polymarket/discovery/worker_lock.py:224` to `packages/polymarket/discovery/worker_lock.py:226`. `_beat_loop()` has no outer `try/except`, no supervision, and no main-thread health check at `packages/polymarket/discovery/worker_lock.py:229` to `packages/polymarket/discovery/worker_lock.py:235`. If the thread target exits unexpectedly, the main process can keep draining while the file mtime stops moving. Another process then sees stale mtime via `_is_stale()` at `packages/polymarket/discovery/worker_lock.py:143` to `packages/polymarket/discovery/worker_lock.py:160`, unlinks at `packages/polymarket/discovery/worker_lock.py:334` to `packages/polymarket/discovery/worker_lock.py:335`, and acquires a lock for a second live drainer.

Concern that does not hold: routine `os.utime()` failure does not kill the thread because `beat()` catches `OSError` and returns `False` at `packages/polymarket/discovery/worker_lock.py:211` to `packages/polymarket/discovery/worker_lock.py:218`. The blocker is the absence of fail-stop/supervision if the daemon thread itself dies independently.

### C. O_EXCL across processes/containers

SHOULD-FIX evidence gap.

The atomicity test is a real race behind a barrier, but it is threads inside one Python process: `threading.Barrier(contenders)` at `tests/test_discovery_shutdown.py:276`, `ThreadPoolExecutor` at `tests/test_discovery_shutdown.py:294`, and the assertion comment at `tests/test_discovery_shutdown.py:297`. There is no multiprocessing/subprocess lock-contention test and no test through the Docker bind mount. The test file also explicitly says it is offline with no Docker/live ClickHouse/live API at `tests/test_discovery_shutdown.py:19`.

### D. mtime precision and clock source

SHOULD-FIX.

The staleness calculation is `age = time.time() - mtime` at `packages/polymarket/discovery/worker_lock.py:152` to `packages/polymarket/discovery/worker_lock.py:160`; heartbeats set mtime via `os.utime(..., None)` at `packages/polymarket/discovery/worker_lock.py:214`. With the default 60s heartbeat and 180s stale threshold, ordinary sub-second/second mtime granularity is unlikely to be the problem. Clock skew between host and container/manual worker is the real sensitivity: a reader clock ahead can falsely reclaim a live holder; a reader clock behind can keep a dead holder fresh.

## Part 3 - Test Reality

What holds:

- Real signal subprocess test: `tests/test_discovery_shutdown.py:66` to `tests/test_discovery_shutdown.py:74` launches `tests/support/sched_sigterm_harness.py`; `tests/test_discovery_shutdown.py:103` to `tests/test_discovery_shutdown.py:107` sends a real signal and waits for bounded exit. This is not a mocked signal.
- Harness uses real `run_scheduler_blocking()` and a real `ScanWorker.run(should_stop=drain_stop_requested)` at `tests/support/sched_sigterm_harness.py:84` to `tests/support/sched_sigterm_harness.py:108`.
- The 12-contender lock test truly races behind a `threading.Barrier` at `tests/test_discovery_shutdown.py:272` to `tests/test_discovery_shutdown.py:295`.
- The heartbeat test uses a real heartbeat thread with `start_heartbeat=True` at `tests/test_discovery_shutdown.py:391` to `tests/test_discovery_shutdown.py:405`.

What does not hold:

- The subprocess test's in-flight wallet work is `time.sleep(0.1)` at `tests/support/sched_sigterm_harness.py:68` to `tests/support/sched_sigterm_harness.py:70`, not the production multi-endpoint scan with retries and CLV calls. It proves between-wallet cancel works for short wallet work; it does not prove Docker 60s grace for real scans.
- The atomicity test does not cover cross-process, cross-container, or bind-mount contention.
- The heartbeat test proves mtime advances for about 0.7s; it does not prove heartbeat supervision or fail-stop if the daemon thread dies.

## Part 4 - Import Hygiene

The evidence report says `tools/cli/discovery.py` removed `signal`/`threading`/`time` imports at `docs/dev_logs/2026-06-04_dr-0-fix.md:81` to `docs/dev_logs/2026-06-04_dr-0-fix.md:82`. Current `git diff -- tools/cli/discovery.py` only shows `import time` removed. Grep found:

- No `from tools.cli.discovery import signal`, `threading`, or `time`.
- No `tools.cli.discovery.signal`, `.threading`, or `.time`.
- Downstream imports are `from tools.cli.discovery import main` in `tests/test_discovery_scheduler.py:435`, `tests/test_discovery_scheduler.py:446`, `tests/test_discovery_scheduler.py:457`, and `tests/test_discovery_scheduler.py:466`, plus module imports as `disc` in tests that do not access those removed names.

No downstream breakage risk found from removed imports.

## Commands Run

```text
git status --short
```

Result: dirty tree with DR-0 files and other ongoing work already present. Review used current on-disk state and did not revert anything.

```text
git log --oneline -5
```

Result:

```text
a2ea5be docs(vault): sync Hermes retirement + Discord notification/bot system
2d16394 docs(vera): Phase B live-verified - approve+deny end-to-end through the gate
c66f375 feat(vera): make /pending cards public (operator-requested), keep author-guard
88e2205 docs(vera): Phase B approve/deny - dev log, feature doc, INDEX, CURRENT_DEVELOPMENT
02120ae fix(vera): make approve/deny reservation fail-safe (Codex re-review)
```

```text
python -m polytool --help
```

Result: exit 0; CLI help loaded and listed commands including `discovery`.

```text
python -m pytest tests/test_discovery_shutdown.py -q
```

Result:

```text
collected 21 items
tests\test_discovery_shutdown.py .....................                   [100%]
21 passed in 3.14s
```

## Verdict

No. DR-0 is not safe for unattended start/stop. The lock's atomic create, stale-only force, and fail-closed paths are substantially improved, and the original 30-minute age-expiry bug is closed in the narrow mtime-heartbeat code path. But the shutdown/tick blocker is not genuinely closed because one production wallet scan can exceed Docker's 60s grace before `should_stop` is checked again. Probe B also surfaces a new blocking heartbeat-supervision gap: a live main process can outlive its daemon heartbeat and later look stale.

Must close before DR-0 can be considered safe:

- Add a real per-wallet shutdown budget or deadline propagated through scan stages/retries/CLV, or make the in-flight wallet interruptible/cancellable before Docker grace expires.
- Make heartbeat liveness fail-stop or supervised: if the heartbeat cannot be proven alive, the drainer must stop or refuse to continue, not silently keep draining until the lock goes stale.
- Add process-level lock contention proof, preferably on the actual `./artifacts:/app/artifacts` deployment mount.
- Document or eliminate host/container clock-skew sensitivity in mtime staleness.
