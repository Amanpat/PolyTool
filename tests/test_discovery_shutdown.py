"""DR-0-FIX Start/Stop Safety — tests that exercise the REAL failures.

The first DR-0 cut shipped five concurrency/lifecycle blockers that its tests
missed because they were synthetic (set an Event directly, raise from a callable,
sequential lock calls). This suite replaces that theater:

1. Bounded cooperative shutdown — a REAL OS signal to a REAL subprocess running
   run_scheduler_blocking() + a REAL ScanWorker drain must exit within a bounded
   time, and a shutdown failure must propagate to a non-zero exit code.
2. Cooperative cancel — the REAL ScanWorker.run() stops BETWEEN wallets on the
   stop flag (no new wallet started), in-flight wallet abandoned without RIS
   corruption.
3. Lock atomicity — REAL concurrent contenders race the O_EXCL primitive; exactly
   one wins.
4. Heartbeat liveness — a live lock (fresh mtime) is NEVER reclaimed even with an
   old acquired_at or via --force; a heartbeat-stale lock IS reclaimed.
5. Fail closed — an unwritable lock path refuses (raises), never drains unlocked.

Offline + stdlib only; no Docker / live ClickHouse / live API.
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from packages.polymarket.discovery.models import QueueState
from packages.polymarket.discovery.scan_queue import ScanQueueManager
from packages.polymarket.discovery.scan_worker import ScanWorker
from packages.polymarket.discovery.worker_lock import (
    WorkerLock,
    WorkerLockError,
    WorkerLockHeld,
    acquire_worker_lock,
)

_HARNESS = str(Path(__file__).resolve().parent / "support" / "sched_sigterm_harness.py")


# ---------------------------------------------------------------------------
# 1. Bounded shutdown — REAL subprocess + REAL signal (Blocker 1 + should-fix 10)
# ---------------------------------------------------------------------------


def _terminate_signal_and_flags():
    """Platform terminate-request signal Python can HANDLE + Popen creationflags.

    POSIX: SIGTERM (docker stop). Windows: CTRL_BREAK_EVENT to the child's own
    process group (SIGTERM is not catchable on Windows; CTRL_BREAK maps to
    SIGBREAK, which run_scheduler_blocking registers).
    """
    if os.name == "nt":
        return signal.CTRL_BREAK_EVENT, subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
    return signal.SIGTERM, 0


def _spawn_harness(mode: str) -> subprocess.Popen:
    _sig, flags = _terminate_signal_and_flags()
    return subprocess.Popen(
        [sys.executable, _HARNESS, mode],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        creationflags=flags,
    )


def _wait_for_ready(proc: subprocess.Popen, timeout: float) -> bool:
    """Block until the child prints READY (draining a pipe in a reader thread)."""
    found = threading.Event()
    captured: list[str] = []

    def _reader() -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            captured.append(line)
            if "READY" in line:
                found.set()

    threading.Thread(target=_reader, daemon=True).start()
    ok = found.wait(timeout)
    proc._harness_output = captured  # type: ignore[attr-defined]
    return ok


class TestBoundedShutdownSubprocess:
    def test_sigterm_exits_bounded_and_clean(self) -> None:
        """A real SIGTERM mid-drain exits within a bounded time with code 0,
        and stops cooperatively (well before the ~60s un-stopped drain)."""
        stop_sig, _flags = _terminate_signal_and_flags()
        proc = _spawn_harness("clean")
        try:
            assert _wait_for_ready(proc, timeout=30.0), "harness never reached READY"
            t0 = time.monotonic()
            proc.send_signal(stop_sig)
            try:
                rc = proc.wait(timeout=20.0)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
                pytest.fail(
                    "scheduler did not exit within 20s of the stop signal "
                    "(unbounded shutdown blocker)"
                )
            elapsed = time.monotonic() - t0
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()

        out = "".join(getattr(proc, "_harness_output", []))
        assert rc == 0, f"expected clean exit 0, got {rc}. Output:\n{out}"
        # The un-stopped drain runs ~60s; a cooperative stop is ~1s. Generous bound.
        assert elapsed < 15.0, (
            f"shutdown took {elapsed:.1f}s — should be bounded/cooperative. Output:\n{out}"
        )

    def test_shutdown_failure_propagates_nonzero_exit(self) -> None:
        """When scheduler.shutdown() fails, the process exits non-zero (not a
        silent 'stopped cleanly')."""
        stop_sig, _flags = _terminate_signal_and_flags()
        proc = _spawn_harness("fail")
        try:
            assert _wait_for_ready(proc, timeout=30.0), "harness never reached READY"
            proc.send_signal(stop_sig)
            try:
                rc = proc.wait(timeout=20.0)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
                pytest.fail("scheduler did not exit within 20s on the failure path")
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()

        out = "".join(getattr(proc, "_harness_output", []))
        assert rc == 1, f"expected non-zero exit 1 on shutdown failure, got {rc}. Output:\n{out}"


# ---------------------------------------------------------------------------
# 2. Cooperative cancel — REAL ScanWorker.run() stops BETWEEN wallets (Blocker 1)
# ---------------------------------------------------------------------------


def _enqueue(queue: ScanQueueManager, wallet: str) -> str:
    return queue.enqueue(wallet, source="manual", priority=3).dedup_key


class TestCooperativeCancel:
    def test_stops_between_wallets_no_new_wallet_started(self) -> None:
        queue = ScanQueueManager()
        keys = [_enqueue(queue, f"0x{i:040x}") for i in range(3)]

        processed: list[str] = []

        def _scan(wallet: str, _flags: dict) -> str:
            processed.append(wallet)
            return f"/tmp/{wallet}"

        worker = ScanWorker(queue, scan_callable=_scan, owner="w")
        # Stop becomes true after the first wallet completes -> the loop must
        # break before leasing the second wallet.
        result = worker.run(max_items=10, should_stop=lambda: len(processed) >= 1)

        assert result.completed == 1
        assert len(processed) == 1  # NO new wallet was started after the stop
        pending_keys = {r.dedup_key for r in queue.get_pending()}
        assert keys[1] in pending_keys and keys[2] in pending_keys
        # The untouched wallets are still pending (not leased, not failed).
        assert queue._items[keys[1]].queue_state == QueueState.pending
        assert queue._items[keys[2]].queue_state == QueueState.pending

    def test_stop_before_first_wallet_does_no_work(self) -> None:
        queue = ScanQueueManager()
        _enqueue(queue, "0xabc")
        called: list[str] = []

        worker = ScanWorker(
            queue,
            scan_callable=lambda w, f: called.append(w) or f"/tmp/{w}",
            owner="w",
        )
        result = worker.run(max_items=5, should_stop=lambda: True)

        assert called == []  # already stopping -> never scanned
        assert result.completed == 0 and result.leased == 0


# ---------------------------------------------------------------------------
# 3. Interrupted-scan recovery — all-or-nothing + lease re-queue (data safety)
# ---------------------------------------------------------------------------


class TestInterruptedScanRecovery:
    def test_killed_scan_does_not_advance_lifecycle_and_marks_failed(self) -> None:
        queue = ScanQueueManager()
        dedup_key = _enqueue(queue, "0xabc")
        advanced: list = []

        def _exploding_scan(wallet: str, flags: dict) -> str:
            raise RuntimeError("scan subprocess killed mid-flight")

        worker = ScanWorker(
            queue,
            scan_callable=_exploding_scan,
            watchlist_advancer=lambda w, r: advanced.append(w),
            owner="scan-worker",
            lease_seconds=300,
            max_attempts=5,
        )
        result = worker.run(max_items=1)

        assert result.leased == 1 and result.failed == 1 and result.completed == 0
        assert advanced == []  # all-or-nothing: never advanced on a killed scan
        item = queue._items[dedup_key]
        assert item.queue_state == QueueState.failed
        assert item.attempt_count == 1

    def test_no_dossier_ingest_on_killed_scan(self) -> None:
        queue = ScanQueueManager()
        _enqueue(queue, "0xabc")
        ingested: list = []

        def _exploding_scan(wallet: str, flags: dict) -> str:
            raise RuntimeError("process killed before dossier produced")

        worker = ScanWorker(
            queue,
            scan_callable=_exploding_scan,
            post_scan_extractor=lambda run_root, slug, wallet: ingested.append(wallet),
            owner="scan-worker",
        )
        result = worker.run(max_items=1)

        assert result.failed == 1
        assert ingested == []  # RIS ingest never ran -> no half-written state

    def test_expired_lease_requeues_interrupted_item(self) -> None:
        queue = ScanQueueManager()
        dedup_key = _enqueue(queue, "0xabc")

        leased = queue.lease(dedup_key, "dead-worker", lease_duration_seconds=300)
        assert leased is not None and leased.queue_state == QueueState.leased
        # Simulate the worker dying mid-flight: lease left in the past.
        leased.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)

        requeued = queue.requeue_expired_leases()

        assert requeued == 1
        item = queue._items[dedup_key]
        assert item.queue_state == QueueState.pending
        assert item.lease_owner is None
        assert item.attempt_count == 1
        assert any(r.dedup_key == dedup_key for r in queue.get_pending())


# ---------------------------------------------------------------------------
# 4. Lock atomicity — REAL concurrent contenders (Blocker 4)
# ---------------------------------------------------------------------------


class TestLockAtomicity:
    def test_concurrent_acquire_exactly_one_winner(self, tmp_path) -> None:  # noqa: ANN001
        lock_file = tmp_path / "worker.lock"
        contenders = 12
        barrier = threading.Barrier(contenders)
        winners: list[WorkerLock] = []
        refused = 0
        lock = threading.Lock()

        def _try() -> None:
            nonlocal refused
            barrier.wait()  # release all contenders at once -> real race
            try:
                wl = acquire_worker_lock(
                    "racer", lock_path=lock_file
                )
                with lock:
                    winners.append(wl)
            except (WorkerLockHeld, WorkerLockError):
                with lock:
                    refused += 1

        with ThreadPoolExecutor(max_workers=contenders) as ex:
            list(ex.map(lambda _f: _f(), [_try] * contenders))

        # O_EXCL guarantees exactly one creator; everyone else is refused.
        assert len(winners) == 1, f"expected 1 winner, got {len(winners)}"
        assert refused == contenders - 1
        assert lock_file.exists()


# ---------------------------------------------------------------------------
# 5. Heartbeat liveness — live never reclaimed, stale reclaimed (Blockers 2/3, force)
# ---------------------------------------------------------------------------


def _write_lock_body(path: Path, *, owner: str, pid: int, acquired_at: str, interval: float = 60.0) -> None:
    path.write_text(
        json.dumps(
            {
                "owner": owner,
                "pid": pid,
                "acquired_at": acquired_at,
                "heartbeat_interval": interval,
            }
        ),
        encoding="utf-8",
    )


def _set_mtime(path: Path, seconds_ago: float) -> None:
    t = time.time() - seconds_ago
    os.utime(path, (t, t))


class TestHeartbeatLiveness:
    def test_live_lock_with_old_acquired_at_is_not_reclaimed(self, tmp_path) -> None:  # noqa: ANN001
        """The 30-minute-age bug fix: an old acquired_at with a FRESH heartbeat
        (recent mtime) is a LIVE holder and must NOT be reclaimed."""
        lock_file = tmp_path / "worker.lock"
        three_hours_ago = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
        _write_lock_body(lock_file, owner="scheduler", pid=os.getpid(), acquired_at=three_hours_ago)
        _set_mtime(lock_file, seconds_ago=5)  # heartbeat just happened -> live

        with pytest.raises(WorkerLockHeld) as exc:
            acquire_worker_lock("scan-worker", lock_path=lock_file)
        assert exc.value.info is not None and exc.value.info.owner == "scheduler"

    def test_heartbeat_stale_lock_is_reclaimed(self, tmp_path) -> None:  # noqa: ANN001
        """No heartbeat within the threshold (old mtime) -> reclaimable."""
        lock_file = tmp_path / "worker.lock"
        _write_lock_body(
            lock_file,
            owner="crashed",
            pid=os.getpid(),
            acquired_at=datetime.now(timezone.utc).isoformat(),
        )
        _set_mtime(lock_file, seconds_ago=1000)  # >> 3*60s threshold

        wl = acquire_worker_lock("scan-worker", lock_path=lock_file)
        assert wl.info.owner == "scan-worker"

    def test_force_refuses_live_lock(self, tmp_path) -> None:  # noqa: ANN001
        """--force must NOT stomp a live holder (two-drainers-impossible)."""
        lock_file = tmp_path / "worker.lock"
        _write_lock_body(
            lock_file,
            owner="scheduler",
            pid=os.getpid(),
            acquired_at=datetime.now(timezone.utc).isoformat(),
        )
        _set_mtime(lock_file, seconds_ago=5)  # live

        with pytest.raises(WorkerLockHeld):
            acquire_worker_lock("scan-worker", lock_path=lock_file, force=True)

    def test_force_reclaims_stale_lock(self, tmp_path) -> None:  # noqa: ANN001
        lock_file = tmp_path / "worker.lock"
        _write_lock_body(
            lock_file,
            owner="crashed",
            pid=os.getpid(),
            acquired_at=datetime.now(timezone.utc).isoformat(),
        )
        _set_mtime(lock_file, seconds_ago=1000)  # stale

        wl = acquire_worker_lock("scan-worker", lock_path=lock_file, force=True)
        assert wl.info.owner == "scan-worker"

    def test_corrupt_body_with_fresh_heartbeat_is_not_reclaimed(self, tmp_path) -> None:  # noqa: ANN001
        """A live holder with an unreadable body must still not be stomped — mtime
        decides staleness, not the body."""
        lock_file = tmp_path / "worker.lock"
        lock_file.write_text("{ not json", encoding="utf-8")
        _set_mtime(lock_file, seconds_ago=5)  # fresh -> live

        with pytest.raises(WorkerLockHeld):
            acquire_worker_lock("scan-worker", lock_path=lock_file)

    def test_beat_refreshes_mtime(self, tmp_path) -> None:  # noqa: ANN001
        """A single beat() call (the holder's main-loop refresh) bumps mtime."""
        lock_file = tmp_path / "worker.lock"
        wl = acquire_worker_lock("scheduler", lock_path=lock_file)
        try:
            _set_mtime(lock_file, seconds_ago=100)  # simulate time passing
            assert wl.beat() is True
            age = time.time() - lock_file.stat().st_mtime
            assert age < 5.0, "beat() did not refresh the lock mtime"
        finally:
            assert wl.release() is True
        assert not lock_file.exists()


# ---------------------------------------------------------------------------
# 5b. Heartbeat supervision (Blocker 2) — NO unsupervised background thread;
#     the holder refreshes from its own main loop, so it cannot die silently.
# ---------------------------------------------------------------------------


class TestHeartbeatSupervision:
    def test_acquire_starts_no_background_thread(self, tmp_path) -> None:  # noqa: ANN001
        """There is no separate heartbeat thread that can die while the holder
        lives (re-review Blocker 2). Acquiring a lock spawns ZERO threads."""
        lock_file = tmp_path / "worker.lock"
        before = threading.active_count()
        wl = acquire_worker_lock("scheduler", lock_path=lock_file)
        try:
            after = threading.active_count()
            assert after == before, (
                f"acquire spawned a background thread ({before} -> {after}); the "
                "unsupervised-heartbeat reclaim hole is back"
            )
            # WorkerLock carries no thread/stop machinery at all.
            assert not hasattr(wl, "_thread")
            assert not hasattr(wl, "_stop")
        finally:
            wl.release()

    def test_scheduler_main_loop_refreshes_lock(self, tmp_path) -> None:  # noqa: ANN001
        """run_scheduler_blocking refreshes the lock from its OWN main loop (no
        thread). The mtime advances across poll cycles while it blocks, then a
        real signal stops it."""
        from packages.research.scheduling.discovery_scheduler import (
            clear_drain_stop,
            run_scheduler_blocking,
        )

        clear_drain_stop()
        lock_file = tmp_path / "worker.lock"
        wl = acquire_worker_lock("scheduler", lock_path=lock_file)
        _set_mtime(lock_file, seconds_ago=100)  # stale-looking until the loop beats

        class _Sched:
            def __init__(self):
                self.calls = []

            def shutdown(self, wait=True):  # noqa: ANN001
                self.calls.append(wait)

        observed: dict = {}
        stopper = threading.Event()

        def _on_started() -> None:
            # Let a few poll cycles run (each calls heartbeat), then stop.
            def _watch():
                time.sleep(0.5)
                observed["mtime_during"] = lock_file.stat().st_mtime
                # Trigger the wait loop to exit via the cooperative path.
                from packages.research.scheduling.discovery_scheduler import request_drain_stop
                request_drain_stop()
                stopper.set()

            threading.Thread(target=_watch, daemon=True).start()

        try:
            # install_signal_handlers=False so this runs cleanly off the main thread
            # of the test; the wait loop still exits via request_drain_stop().
            rc = run_scheduler_blocking(
                _Sched(),
                poll_seconds=0.1,
                shutdown_wait=False,
                install_signal_handlers=False,
                on_started=_on_started,
                heartbeat=wl.beat,
            )
            assert stopper.wait(5.0)
            # The main loop refreshed the lock well within the stale threshold.
            age_during = time.time() - observed["mtime_during"]
            assert age_during < 5.0, "main-loop heartbeat did not refresh the lock"
            assert rc == 0
        finally:
            clear_drain_stop()  # do not leak the module stop flag to other tests
            wl.release()

    def test_manual_worker_beats_between_wallets(self, tmp_path) -> None:  # noqa: ANN001
        """The manual worker refreshes the lock between wallets (no thread), so a
        long bounded drain on the main thread never lets the lock go stale."""
        lock_file = tmp_path / "worker.lock"
        wl = acquire_worker_lock("scan-worker", lock_path=lock_file)
        try:
            queue = ScanQueueManager()
            for i in range(3):
                _enqueue(queue, f"0x{i:040x}")
            _set_mtime(lock_file, seconds_ago=100)  # stale until a beat happens

            def _scan(wallet: str, _flags: dict) -> str:
                return f"/tmp/{wallet}"

            worker = ScanWorker(queue, scan_callable=_scan, owner="scan-worker")
            worker.run(max_items=3, heartbeat=wl.beat)

            age = time.time() - lock_file.stat().st_mtime
            assert age < 5.0, "manual worker did not refresh the lock between wallets"
        finally:
            wl.release()


# ---------------------------------------------------------------------------
# 6. Fail closed — unwritable lock path refuses (Blocker 5)
# ---------------------------------------------------------------------------


class TestFailClosed:
    def test_unwritable_lock_dir_refuses(self, tmp_path) -> None:  # noqa: ANN001
        """If the lock dir cannot be created (parent is a FILE), acquisition
        raises WorkerLockError — the caller refuses to run, never drains unlocked."""
        blocker = tmp_path / "blocker"
        blocker.write_text("i am a file, not a dir", encoding="utf-8")
        lock_file = blocker / "worker.lock"  # parent is a file -> mkdir fails

        with pytest.raises(WorkerLockError):
            acquire_worker_lock("scan-worker", lock_path=lock_file)
        # And no lock file was somehow created.
        assert not lock_file.exists()


# ---------------------------------------------------------------------------
# 7. Lock release ownership + second-acquire refusal (basic guards)
# ---------------------------------------------------------------------------


class TestLockReleaseAndRefusal:
    def test_second_acquire_refused_while_live(self, tmp_path) -> None:  # noqa: ANN001
        lock_file = tmp_path / "worker.lock"
        wl = acquire_worker_lock("discovery-scheduler", lock_path=lock_file)
        try:
            assert wl.info.owner == "discovery-scheduler"
            with pytest.raises(WorkerLockHeld) as exc:
                acquire_worker_lock("scan-worker", lock_path=lock_file)
            assert exc.value.info is not None and exc.value.info.owner == "discovery-scheduler"
        finally:
            wl.release()

    def test_release_only_when_owned(self, tmp_path) -> None:  # noqa: ANN001
        lock_file = tmp_path / "worker.lock"
        wl = acquire_worker_lock("scan-worker", lock_path=lock_file)

        # A foreign PID now owns the file on disk -> we must NOT delete it.
        _write_lock_body(
            lock_file,
            owner="someone-else",
            pid=999999,
            acquired_at=datetime.now(timezone.utc).isoformat(),
        )
        assert wl.release() is False
        assert lock_file.exists()

        # Restore our ownership -> release succeeds.
        _write_lock_body(
            lock_file,
            owner="scan-worker",
            pid=os.getpid(),
            acquired_at=datetime.now(timezone.utc).isoformat(),
        )
        assert wl.release() is True
        assert not lock_file.exists()


# ---------------------------------------------------------------------------
# 8. stop_discovery_scheduler helper contract (unit)
# ---------------------------------------------------------------------------


class _FakeScheduler:
    def __init__(self, *, shutdown_raises: bool = False, accepts_wait: bool = True) -> None:
        self.shutdown_calls: list = []
        self._shutdown_raises = shutdown_raises
        self._accepts_wait = accepts_wait

    def shutdown(self, *args, **kwargs):  # noqa: ANN002, ANN003
        if not self._accepts_wait and (args or kwargs):
            raise TypeError("shutdown() takes no arguments")
        self.shutdown_calls.append({"args": args, "kwargs": kwargs})
        if self._shutdown_raises:
            raise RuntimeError("boom during shutdown")


class TestStopDiscoveryScheduler:
    def test_shutdown_called_with_wait_flag(self) -> None:
        from packages.research.scheduling.discovery_scheduler import stop_discovery_scheduler

        sched = _FakeScheduler()
        assert stop_discovery_scheduler(sched, wait=False) is True
        assert sched.shutdown_calls[0]["kwargs"] == {"wait": False}

    def test_falls_back_to_no_arg_shutdown(self) -> None:
        from packages.research.scheduling.discovery_scheduler import stop_discovery_scheduler

        sched = _FakeScheduler(accepts_wait=False)
        assert stop_discovery_scheduler(sched, wait=True) is True
        assert sched.shutdown_calls == [{"args": (), "kwargs": {}}]

    def test_never_raises_on_shutdown_error_returns_false(self) -> None:
        from packages.research.scheduling.discovery_scheduler import stop_discovery_scheduler

        sched = _FakeScheduler(shutdown_raises=True)
        assert stop_discovery_scheduler(sched, wait=False) is False

    def test_none_scheduler_is_safe(self) -> None:
        from packages.research.scheduling.discovery_scheduler import stop_discovery_scheduler

        assert stop_discovery_scheduler(None) is False


# ---------------------------------------------------------------------------
# 9. Request-granularity cancel (DR-0-FIX-2 Blocker 1) — REAL slow/retrying HTTP.
#    A stop must abort the IN-FLIGHT request/retry within ~one request timeout
#    (not the full ~67s retry budget), and the partial wallet must NOT ingest.
# ---------------------------------------------------------------------------


class TestRequestGranularityCancel:
    def _start_hanging_server(self):
        """A TCP listener that accepts connections and never responds, so an HTTP
        client times out per attempt (forcing the real retry/backoff path)."""
        import socket

        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.bind(("127.0.0.1", 0))
        srv.listen(8)
        srv.settimeout(0.25)
        port = srv.getsockname()[1]
        held: list = []
        stop = threading.Event()

        def _accept_loop():
            while not stop.is_set():
                try:
                    conn, _ = srv.accept()
                    held.append(conn)  # hold open, never reply
                except OSError:
                    continue

        t = threading.Thread(target=_accept_loop, daemon=True)
        t.start()
        return srv, port, stop, held

    def test_stop_aborts_in_flight_request_and_does_not_ingest(self) -> None:
        """Real ScanWorker over the real scan.py retry loop against a hanging
        endpoint. A stop flipped mid-retry aborts within ~one request timeout and
        the partial wallet is released to pending, never ingested."""
        from tools.cli import scan as scan_mod

        srv, port, stop_srv, _held = self._start_hanging_server()
        timeout_s = 1.0
        retries = 3
        backoff = 0.5
        # Without cancel this is 4*1.0 + (0.5+1+2) = 7.5s. With cancel: ~<=1.5s.

        ingested: list = []
        stop_flag = {"v": False}

        def _scan(wallet: str, _flags: dict) -> str:
            # Drives the REAL retry/backoff loop in scan.py against the hang.
            scan_mod.get_json(
                base_url=f"http://127.0.0.1:{port}",
                path="/hang",
                params={},
                timeout=timeout_s,
                retries=retries,
                backoff_seconds=backoff,
            )
            return f"/tmp/{wallet}"  # never reached

        queue = ScanQueueManager()
        key = _enqueue(queue, "0xdeadbeef")
        worker = ScanWorker(
            queue,
            scan_callable=_scan,
            post_scan_extractor=lambda run_root, slug, wallet: ingested.append(wallet),
            owner="scan-worker",
        )

        # Flip the stop flag shortly after the scan starts (mid first attempt).
        def _flip():
            time.sleep(0.4)
            stop_flag["v"] = True

        threading.Thread(target=_flip, daemon=True).start()

        try:
            t0 = time.monotonic()
            result = worker.run(max_items=1, should_stop=lambda: stop_flag["v"])
            elapsed = time.monotonic() - t0
        finally:
            stop_srv.set()
            srv.close()
            scan_mod.clear_cancel_check()  # belt-and-suspenders

        # Bounded: aborted within ~one request timeout, FAR below the 7.5s budget.
        assert elapsed < 4.0, f"stop took {elapsed:.1f}s — not request-bounded"
        # Cooperative cancel outcome: not ingested, not failed, re-scannable.
        assert ingested == [], "partial wallet must NOT ingest on a cancel"
        assert result.cancelled == 1
        assert result.completed == 0 and result.failed == 0
        assert queue._items[key].queue_state == QueueState.pending
        assert queue._items[key].attempt_count == 0  # no poison-pill attempt burned

    def test_cancellable_sleep_aborts_backoff_fast(self) -> None:
        """The backoff sleep itself is cancellable (not a fixed time.sleep)."""
        from tools.cli import scan as scan_mod

        flag = {"v": False}
        scan_mod.set_cancel_check(lambda: flag["v"])
        try:
            def _flip():
                time.sleep(0.2)
                flag["v"] = True

            threading.Thread(target=_flip, daemon=True).start()
            t0 = time.monotonic()
            with pytest.raises(scan_mod.ScanCancelled):
                scan_mod._cancellable_sleep(10.0)  # would sleep 10s uncancelled
            elapsed = time.monotonic() - t0
            assert elapsed < 1.0, f"cancellable sleep took {elapsed:.1f}s"
        finally:
            scan_mod.clear_cancel_check()

    def test_foreground_path_has_no_cancel_hook(self) -> None:
        """DR-2 gate: with no cancel hook installed, the scan path is unchanged
        (the predicate is None -> never cancels)."""
        from tools.cli import scan as scan_mod

        scan_mod.clear_cancel_check()
        assert scan_mod._scan_cancelled() is False
        # _cancellable_sleep behaves as a normal short sleep when not cancelled.
        t0 = time.monotonic()
        scan_mod._cancellable_sleep(0.1)
        assert time.monotonic() - t0 >= 0.1


# ---------------------------------------------------------------------------
# 10. Two-PROCESS O_EXCL contention (re-review SHOULD-FIX C) — real subprocesses.
# ---------------------------------------------------------------------------

_LOCK_CONTENDER = str(Path(__file__).resolve().parent / "support" / "lock_contender.py")


class TestProcessLevelLockContention:
    def test_two_real_processes_exactly_one_wins(self, tmp_path) -> None:  # noqa: ANN001
        lock_file = tmp_path / "worker.lock"
        go_file = tmp_path / "go"

        def _spawn() -> subprocess.Popen:
            return subprocess.Popen(
                [sys.executable, _LOCK_CONTENDER, str(lock_file), str(go_file)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )

        p1 = _spawn()
        p2 = _spawn()
        try:
            time.sleep(0.4)  # let both reach the barrier
            go_file.write_text("go", encoding="utf-8")
            out1 = p1.communicate(timeout=20)[0].strip()
            out2 = p2.communicate(timeout=20)[0].strip()
        finally:
            for p in (p1, p2):
                if p.poll() is None:
                    p.kill()
                    p.wait()

        results = sorted([out1, out2])
        assert results == ["REFUSED", "WON"], (
            f"expected exactly one WON / one REFUSED across two real processes, "
            f"got {results!r}"
        )
