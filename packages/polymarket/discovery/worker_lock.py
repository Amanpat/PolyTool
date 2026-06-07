"""Single-host advisory lock for the wallet-discovery drainer (DR-0-FIX).

WHY
---
ClickHouse leases are NOT an atomic compare-and-set (documented in
``scan_worker.py`` and the WI-3 scheduler docstring). Two drainers running at
once can double-grab the same ``dedup_key``. The scheduler ``queue_drain`` job
is one bounded tick, but an operator running a *manual* ``discovery run-worker``
while the scheduler container is up would be a second drainer. This module
closes that hole with a single-host advisory lock — NOT a distributed lock, NOT
CAS. The threat model is exactly: "two drainers on one queue must be
impossible."

DR-0-FIX hardening (Codex adversarial review, 2026-06-04)
---------------------------------------------------------
The first cut shipped five concurrency/lifecycle defects. This rewrite closes
the lock ones:

- **Atomic acquisition.** Acquire via ``os.open(O_CREAT|O_EXCL|O_WRONLY)`` — the
  kernel guarantees exactly one creator. No check-then-``write_text`` race.
- **Heartbeat liveness, not age or bare PID.** The holder refreshes the lock
  file mtime on an interval (default 60s). "Stale" means *no heartbeat within
  ~3x the interval*. A live holder that keeps beating NEVER looks stale, so a
  long-lived scheduler is never reclaimed out from under itself. This retires
  the old "lock older than 30 min = stale" bug and the unreliable bare-PID
  liveness probe (PID reuse / Windows always-alive).
- **Fail closed.** If the lock cannot be created or written for any reason other
  than "a live holder already has it," we raise ``WorkerLockError`` and the
  caller refuses to run (non-zero exit). There is no "proceed without a lock"
  path. A stale lock is the ONLY thing reclaimed, and only because staleness
  proves there is no live holder.
- **``force`` cannot stomp a live holder.** ``force`` is retained as an explicit
  reclaim switch but it only ever reclaims a *heartbeat-stale* lock — the same
  thing normal acquisition reclaims. Against a live heartbeat it refuses, so the
  "two drainers impossible" invariant holds even with ``--force``.

DR-0-FIX-2: the heartbeat is NO LONGER a background thread. The holder refreshes
the lock mtime from its own main control loop via ``WorkerLock.beat()`` (the
scheduler from ``run_scheduler_blocking``'s wait loop; the manual worker between
wallets). This removes the "daemon heartbeat thread dies silently while the main
process keeps draining" reclaim hole — the refresher is now the holder's own
liveness, so it cannot die independently of the holder.

SAME-HOST CLOCK ASSUMPTION (re-review SHOULD-FIX D, accepted, not gated):
Staleness compares a reader's ``time.time()`` to the lock file mtime. This is
SAFE ONLY on a single host, where the scheduler container and any manual worker
share the host kernel clock through the ``./artifacts:/app/artifacts`` bind mount
(containers share the host clock; there is no skew). We deliberately do NOT gate
on or correct for clock skew. If a worker is ever run on a SEPARATE machine
against the same lock path (not a supported topology today), this mtime staleness
would need a shared monotonic source instead — revisit only then.

This is deliberately small: stdlib only (``os`` / ``json`` / ``time``), no new
dependency, no background thread, no daemon process.
"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_LOCK_PATH = Path("artifacts") / "discovery" / "worker.lock"

# Heartbeat cadence + staleness threshold. A holder bumps the lock file mtime
# every DEFAULT_HEARTBEAT_INTERVAL seconds; a lock whose mtime is older than
# STALE_MULTIPLIER intervals (with a floor) has no live holder and is reclaimable.
DEFAULT_HEARTBEAT_INTERVAL = 60.0
STALE_MULTIPLIER = 3.0
MIN_STALE_SECONDS = 30.0  # floor so a tiny interval can't make a live lock flicker stale


class WorkerLockError(RuntimeError):
    """The lock could not be established for a reason OTHER than a live holder.

    Acquisition fails closed on this: the caller must refuse to run (non-zero
    exit) rather than drain unlocked.
    """


class WorkerLockHeld(WorkerLockError):
    """A live (heartbeat-fresh) worker lock is already held by another process."""

    def __init__(self, info: Optional["LockInfo"], path: Path) -> None:
        self.info = info
        self.path = path
        if info is not None:
            msg = (
                f"discovery worker lock held by owner={info.owner!r} pid={info.pid} "
                f"since {info.acquired_at} (lock file: {path})"
            )
        else:  # pragma: no cover - defensive; a live-but-unreadable lock
            msg = f"discovery worker lock is held (lock file: {path})"
        super().__init__(msg)


@dataclass(frozen=True)
class LockInfo:
    owner: str
    pid: int
    acquired_at: str  # ISO 8601 UTC (informational; staleness uses mtime, not this)
    heartbeat_interval: float = DEFAULT_HEARTBEAT_INTERVAL


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _payload(info: LockInfo) -> str:
    return json.dumps(
        {
            "owner": info.owner,
            "pid": info.pid,
            "acquired_at": info.acquired_at,
            "heartbeat_interval": info.heartbeat_interval,
        }
    )


def _read_lock(path: Path) -> Optional[LockInfo]:
    """Read the lock body. Returns None if absent; best-effort on corrupt body.

    NOTE: a corrupt/unreadable *body* does not by itself mean reclaimable — the
    caller still consults mtime-based staleness. We return a LockInfo with a
    default interval so staleness can be computed; owner/pid are unknown.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError as exc:
        logger.warning("worker_lock: could not read lock file %s: %s", path, exc)
        # Unknown body but the file exists -> let mtime decide staleness.
        return LockInfo(owner="unknown", pid=-1, acquired_at="", heartbeat_interval=DEFAULT_HEARTBEAT_INTERVAL)
    try:
        d = json.loads(raw)
        return LockInfo(
            owner=str(d.get("owner", "unknown")),
            pid=int(d.get("pid", -1)),
            acquired_at=str(d.get("acquired_at", "")),
            heartbeat_interval=float(d.get("heartbeat_interval", DEFAULT_HEARTBEAT_INTERVAL)),
        )
    except (ValueError, TypeError) as exc:
        logger.warning("worker_lock: malformed lock body %s (%s)", path, exc)
        return LockInfo(owner="unknown", pid=-1, acquired_at="", heartbeat_interval=DEFAULT_HEARTBEAT_INTERVAL)


def _stale_threshold(interval: float) -> float:
    return max(MIN_STALE_SECONDS, STALE_MULTIPLIER * float(interval or DEFAULT_HEARTBEAT_INTERVAL))


def _is_stale(path: Path, info: Optional[LockInfo], *, now: Optional[float] = None) -> bool:
    """Heartbeat staleness: True iff no heartbeat (mtime bump) within the threshold.

    A live holder refreshes the mtime every ``heartbeat_interval`` seconds, so a
    fresh mtime ALWAYS means a live holder (never reclaim it). Only an mtime
    older than ~3x the interval — i.e. a holder that stopped beating (crashed /
    killed) — is stale and reclaimable.
    """
    try:
        mtime = path.stat().st_mtime
    except FileNotFoundError:
        return True  # absent == reclaimable (nothing to hold)
    except OSError as exc:  # pragma: no cover - defensive
        logger.warning("worker_lock: could not stat lock file %s: %s", path, exc)
        return False  # can't prove stale -> treat as live (fail closed, don't stomp)
    interval = info.heartbeat_interval if info is not None else DEFAULT_HEARTBEAT_INTERVAL
    age = (time.time() if now is None else now) - mtime
    return age > _stale_threshold(interval)


def _exclusive_create(path: Path, payload: str) -> bool:
    """Atomically create the lock file. True if WE created it, False if it exists.

    Raises WorkerLockError on any other failure (fail closed).
    """
    try:
        fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError:
        return False
    except OSError as exc:
        raise WorkerLockError(f"cannot create lock file {path}: {exc}") from exc
    try:
        os.write(fd, payload.encode("utf-8"))
    except OSError as exc:  # pragma: no cover - defensive
        os.close(fd)
        # We created an empty/partial lock; remove it so we don't wedge, then fail closed.
        try:
            path.unlink()
        except OSError:
            pass
        raise WorkerLockError(f"cannot write lock file {path}: {exc}") from exc
    os.close(fd)
    return True


class WorkerLock:
    """An acquired single-host worker lock, refreshed by the holder's MAIN loop.

    Use ``acquire_worker_lock(...)`` to construct one. Always release via
    ``release()`` (a broad ``try/finally`` in the caller).

    DR-0-FIX-2: there is NO background heartbeat thread. The original design used
    an unsupervised daemon thread that could die silently while the main process
    kept draining — after ~180s the mtime looked stale and a second worker could
    reclaim a LIVE lock (re-review Blocker 2). Instead, the holder refreshes the
    heartbeat from its own main control loop by calling ``beat()``:

      - the scheduler beats from ``run_scheduler_blocking``'s wait loop (wakes
        every ~60s on the main thread, even while a drain runs on a job thread);
      - the manual worker beats between wallets inside ``ScanWorker.run``.

    Because the refresher IS the holder's own liveness, there is no separate
    thread that can die independently: if the holder is alive it beats; if it is
    dead it stops beating and the lock correctly goes stale.
    """

    def __init__(self, path: Path, info: LockInfo) -> None:
        self._path = path
        self._info = info

    @property
    def info(self) -> LockInfo:
        return self._info

    @property
    def path(self) -> Path:
        return self._path

    def beat(self) -> bool:
        """Refresh the heartbeat (bump mtime). Best-effort; returns success.

        Called from the holder's main loop — NOT from a background thread.
        """
        try:
            os.utime(self._path, None)
            return True
        except OSError as exc:  # pragma: no cover - defensive
            logger.warning("worker_lock: heartbeat failed for %s: %s", self._path, exc)
            return False

    def release(self) -> bool:
        """Remove the lock file iff we still own it (no thread to stop)."""
        current = _read_lock(self._path)
        if current is not None and current.pid not in (self._info.pid, -1):
            logger.info(
                "worker_lock: not releasing lock now owned by pid=%s (we are pid=%s)",
                current.pid,
                self._info.pid,
            )
            return False
        try:
            self._path.unlink()
            return True
        except FileNotFoundError:
            return False
        except OSError as exc:  # pragma: no cover - defensive
            logger.warning("worker_lock: could not remove lock file %s: %s", self._path, exc)
            return False


def acquire_worker_lock(
    owner: str,
    *,
    lock_path: Path = DEFAULT_LOCK_PATH,
    force: bool = False,
    heartbeat_interval: float = DEFAULT_HEARTBEAT_INTERVAL,
    _now: Optional[float] = None,
) -> WorkerLock:
    """Acquire the single-host discovery worker lock (atomic, fail-closed).

    Args:
        owner: Human-readable holder label ("scan-worker" / "discovery-scheduler").
        lock_path: Lock file path (default ``artifacts/discovery/worker.lock``).
        force: Explicit reclaim switch. It only ever reclaims a *heartbeat-stale*
            lock (same as normal acquisition); it CANNOT override a live holder.
        heartbeat_interval: Seconds the holder's main loop should leave between
            ``beat()`` refreshes; recorded so a reader derives the stale threshold.
        _now: Injected wall clock for staleness (tests only).

    Returns:
        The acquired ``WorkerLock``. NO background thread is started — the holder
        must refresh via ``beat()`` from its own main loop (see ``WorkerLock``).

    Raises:
        WorkerLockHeld: a live (heartbeat-fresh) lock is held.
        WorkerLockError: the lock could not be established (dir/file unwritable,
            lost reclaim race) — caller must refuse to run.
    """
    path = Path(lock_path)
    info = LockInfo(
        owner=owner,
        pid=os.getpid(),
        acquired_at=_iso_now(),
        heartbeat_interval=float(heartbeat_interval),
    )
    payload = _payload(info)

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        # Fail closed: no writable lock dir -> never drain unlocked.
        raise WorkerLockError(f"cannot create lock directory {path.parent}: {exc}") from exc

    # Try atomic create; on contention, reclaim ONLY a heartbeat-stale lock.
    # One reclaim retry covers a stale->race (another process reclaimed first).
    for _attempt in range(2):
        if _exclusive_create(path, payload):
            return WorkerLock(path, info)

        existing = _read_lock(path)
        if not _is_stale(path, existing, now=_now):
            # Live holder. force CANNOT stomp it — the invariant is "two drainers
            # impossible." Refuse regardless of force.
            raise WorkerLockHeld(existing, path)

        # Stale: provably no live holder. Reclaim (force flag is informational
        # here; stale is reclaimed either way). Remove, then loop retries O_EXCL.
        if force:
            logger.warning(
                "worker_lock: reclaiming heartbeat-stale lock (owner=%r pid=%s) via --force",
                getattr(existing, "owner", "?"),
                getattr(existing, "pid", "?"),
            )
        else:
            logger.info(
                "worker_lock: reclaiming heartbeat-stale lock (owner=%r pid=%s)",
                getattr(existing, "owner", "?"),
                getattr(existing, "pid", "?"),
            )
        try:
            path.unlink()
        except FileNotFoundError:
            pass  # someone else reclaimed concurrently; retry the exclusive create
        except OSError as exc:
            raise WorkerLockError(f"cannot reclaim stale lock {path}: {exc}") from exc

    # Lost the reclaim race twice -> a live holder now owns it. Fail closed.
    raise WorkerLockHeld(_read_lock(path), path)
