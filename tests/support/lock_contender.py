"""Subprocess contender for the two-process O_EXCL lock test (NOT a pytest file).

Spawned twice by ``tests/test_discovery_shutdown.py``. Both copies wait on a
barrier file the parent creates, then race ``acquire_worker_lock`` on the SAME
lock path as REAL separate OS processes (re-review SHOULD-FIX C — the prior test
was threads-in-one-process only). Exactly one must print WON.

Usage:  python lock_contender.py <lock_path> <go_file>
Prints: "WON" (acquired) or "REFUSED" (live lock held by the other process).
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from packages.polymarket.discovery.worker_lock import (  # noqa: E402
    WorkerLockError,
    WorkerLockHeld,
    acquire_worker_lock,
)


def main() -> int:
    lock_path = Path(sys.argv[1])
    go_file = Path(sys.argv[2])

    # Barrier: spin until the parent says go, so both processes race together.
    for _ in range(4000):
        if go_file.exists():
            break
        time.sleep(0.005)

    try:
        lock = acquire_worker_lock("contender", lock_path=lock_path)
    except (WorkerLockHeld, WorkerLockError):
        print("REFUSED", flush=True)
        return 0

    # Hold long enough that the loser definitely sees a LIVE (fresh-mtime) lock
    # and is refused — not a stale one it could reclaim.
    print("WON", flush=True)
    time.sleep(2.0)
    lock.release()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
