"""Subprocess harness for the DR-0-FIX bounded-shutdown test (NOT a pytest file).

Run as a child process by ``tests/test_discovery_shutdown.py``. It wires the REAL
shutdown path end to end — no mocks of the logic under test:

  real OS signal (SIGTERM / CTRL_BREAK)
    -> real run_scheduler_blocking() signal handler
    -> real request_drain_stop()
    -> real ScanWorker.run(should_stop=drain_stop_requested) breaking BETWEEN wallets
    -> real stop_discovery_scheduler(wait=False)

The in-flight drain is a genuine ScanWorker on a real (in-memory) queue with 600
"wallets", each taking ~0.1s. Left alone it runs ~60s. A correct cooperative stop
makes the process exit within ~1s of the signal.

Exit codes:
  0  -> clean: shutdown returned 0 AND the drain stopped cooperatively (early).
  1  -> shutdown reported failure (used by the "fail" mode to prove non-zero exit).
  98 -> the drain did NOT stop early (cooperative cancel broken) / still running.
  99 -> unexpected internal error.

Usage:  python sched_sigterm_harness.py [clean|fail]
"""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

# Make the repo importable when launched by file path from a child process.
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from packages.polymarket.discovery.scan_queue import ScanQueueManager  # noqa: E402
from packages.polymarket.discovery.scan_worker import ScanWorker  # noqa: E402
from packages.research.scheduling.discovery_scheduler import (  # noqa: E402
    clear_drain_stop,
    drain_stop_requested,
    run_scheduler_blocking,
)

_WALLET_COUNT = 600
_PER_WALLET_SECONDS = 0.1  # 600 * 0.1s = ~60s if never stopped


class _FakeScheduler:
    """Stands in for APScheduler. ``fail`` makes shutdown raise (non-zero exit)."""

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.shutdown_calls: list = []

    def shutdown(self, wait: bool = True):  # noqa: ANN001
        self.shutdown_calls.append(wait)
        if self.fail:
            raise RuntimeError("simulated shutdown failure")


def main(mode: str) -> int:
    clear_drain_stop()

    queue = ScanQueueManager()
    for i in range(_WALLET_COUNT):
        queue.enqueue(f"0x{i:040x}", source="manual", priority=3)

    def _slow_scan(wallet: str, _flags: dict) -> str:
        # One "wallet" of bounded work. No network, no ClickHouse.
        time.sleep(_PER_WALLET_SECONDS)
        return f"/tmp/run/{wallet}"

    worker = ScanWorker(
        queue,
        scan_callable=_slow_scan,
        owner="sigterm-harness",
        lease_seconds=300,
        max_attempts=5,
    )

    result_holder: dict = {}
    drain_done = threading.Event()

    def _drain() -> None:
        # The REAL cooperative break: should_stop is the real module flag the
        # signal handler sets via request_drain_stop().
        res = worker.run(max_items=_WALLET_COUNT, should_stop=drain_stop_requested)
        result_holder["completed"] = res.completed
        drain_done.set()

    # Non-daemon, like APScheduler's executor threads: the process cannot exit
    # until this thread returns, so a bounded exit PROVES the cooperative break.
    drain_thread = threading.Thread(target=_drain, name="harness-drain", daemon=False)
    sched = _FakeScheduler(fail=(mode == "fail"))

    def _on_started() -> None:
        drain_thread.start()
        # Ensure we are genuinely mid-drain (at least one wallet in flight)
        # before announcing readiness.
        time.sleep(_PER_WALLET_SECONDS * 3)
        print("READY", flush=True)

    code = run_scheduler_blocking(
        sched,
        poll_seconds=0.2,
        shutdown_wait=False,
        on_started=_on_started,
    )

    drain_thread.join(timeout=10.0)

    if mode == "fail":
        # Prove shutdown failure propagates to a non-zero exit code.
        return code if code != 0 else 99

    # Clean mode: must have stopped cooperatively and early (not all 600 done).
    if drain_thread.is_alive() or not drain_done.is_set():
        return 98
    if result_holder.get("completed", _WALLET_COUNT) >= _WALLET_COUNT:
        return 98  # processed everything -> never broke early
    return code


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "clean"
    try:
        raise SystemExit(main(arg))
    except SystemExit:
        raise
    except BaseException as exc:  # noqa: BLE001 - last-resort diagnostic
        print(f"HARNESS-ERROR: {type(exc).__name__}: {exc}", flush=True)
        raise SystemExit(99)
