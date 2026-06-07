"""Scan queue consumer for Wallet Discovery v1 (WI-1).

The worker drains `scan_queue`: it leases a pending row, runs a wallet scan on
the leased address, extracts the resulting dossier into the RIS KnowledgeStore,
advances the watchlist lifecycle (discovered/queued -> scanned), and marks the
queue row complete. On any failure it marks the row failed (attempt_count is
incremented), letting expired-lease requeue retry it within attempt limits.

This is the connective tissue that turns the individually-built discovery
pieces (leaderboard fetch -> churn -> enqueue) into an end-to-end pipeline.

SINGLE-WORKER ASSUMPTION (WI-1 check #3)
----------------------------------------
ClickHouse is OLAP, not a transactional queue. The in-memory `ScanQueueManager`
lease is NOT an atomic compare-and-set against ClickHouse. With two concurrent
workers, `get_pending() -> lease()` can double-grab the same dedup_key (a
TOCTOU race) and double-scan a wallet. WI-1 runs the worker only in a bounded,
single-process mode (`--once` / `--max-items`), which never triggers the race.
A continuous / multi-worker drain (WP-3) must consciously add real lease
atomicity (e.g. a CAS guard or a dedicated transactional store) before running
more than one worker against the same queue. Do NOT assume this worker is
safe to run concurrently as written.

POISON-PILL / ATTEMPT CEILING (WI-1 check #5)
---------------------------------------------
`ScanQueueManager.fail()` and `requeue_expired_leases()` increment
`attempt_count` but the manager itself enforces NO ceiling — a wallet that
fails forever would requeue forever in a continuous drain. WI-1 runs bounded
(`--once` / `--max-items`) so a single drain cannot loop on one poison pill.
This worker additionally honours a `max_attempts` ceiling: a pending row whose
`attempt_count >= max_attempts` is dead-lettered to `dropped` (a terminal
state) and skipped, so it never re-leases. This keeps a bounded drain from
silently re-scanning a known-bad wallet. Continuous-mode cadence and any
operator-facing dead-letter reporting remain WP-3 concerns.

SPEC: docs/specs/SPEC-wallet-discovery-v1.md section "scan_queue table"
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from packages.polymarket.discovery.models import (
    LifecycleState,
    QueueState,
    ReviewStatus,
    ScanQueueRow,
    WatchlistRow,
)
from packages.polymarket.discovery.scan_queue import ScanQueueManager

logger = logging.getLogger(__name__)

# Scan callable: (wallet_address, scan_flags) -> scan_run_root path string.
# Mirrors tools.cli.wallet_scan.ScanCallable so _default_scan_callable plugs in.
ScanCallable = Callable[[str, dict], str]

# Post-scan dossier extractor: (scan_run_root, slug, wallet) -> None.
# Mirrors tools.cli.wallet_scan.PostScanExtractor; must not raise fatally.
PostScanExtractor = Callable[[Path, str, str], None]

# Watchlist lifecycle-advance hook: (wallet_address, run_root) -> None.
# Injected so offline tests can assert the advance without ClickHouse I/O.
WatchlistAdvancer = Callable[[str, Path], None]

DEFAULT_MAX_ATTEMPTS = 5
DEFAULT_SCAN_FLAGS: dict = {
    "lite": True,
    "ingest_positions": True,
    "compute_pnl": True,
    "enrich_resolutions": True,
    "compute_clv": True,
}


class _NeverCancelled(Exception):
    """Sentinel exception type used when no cancel hook is installed.

    ``except _NeverCancelled`` can never match a real exception, so the
    cooperative-cancel branch is inert unless a stop hook is wired in.
    """


@dataclass
class WorkerResult:
    """Summary of one bounded worker drain."""

    requeued: int = 0
    leased: int = 0
    completed: int = 0
    failed: int = 0
    dropped: int = 0
    skipped: int = 0
    cancelled: int = 0
    processed_keys: list[str] = field(default_factory=list)


class ScanWorker:
    """Bounded consumer that drains the scan queue.

    Dependencies are injected so the worker is fully testable offline with a
    mocked scan callable (no live API, no ClickHouse).

    Parameters
    ----------
    queue:
        The ScanQueueManager holding the in-memory queue state (hydrate it from
        ClickHouse via load_from_clickhouse() before running, if persisting).
    scan_callable:
        Runs the real scan on a wallet address and returns the run_root path.
        Defaults to wallet_scan._default_scan_callable (lazily imported).
    post_scan_extractor:
        Runs dossier extraction + RIS ingestion against the scan run_root.
        Optional; if None, the dossier/ingest step is skipped (scan-only drain).
    watchlist_advancer:
        Advances the watchlist lifecycle to 'scanned' on success. Optional; if
        None, the lifecycle is not touched (e.g. dry-run / offline tests).
    owner:
        Lease owner identifier recorded on each leased row.
    lease_seconds:
        Lease TTL in seconds.
    max_attempts:
        Attempt ceiling. A pending row with attempt_count >= max_attempts is
        dead-lettered to 'dropped' and skipped (poison-pill guard).
    """

    def __init__(
        self,
        queue: ScanQueueManager,
        *,
        scan_callable: Optional[ScanCallable] = None,
        post_scan_extractor: Optional[PostScanExtractor] = None,
        watchlist_advancer: Optional[WatchlistAdvancer] = None,
        owner: str = "scan-worker",
        lease_seconds: int = 300,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        scan_flags: Optional[dict] = None,
    ) -> None:
        self._queue = queue
        self._scan_callable = scan_callable
        self._post_scan_extractor = post_scan_extractor
        self._watchlist_advancer = watchlist_advancer
        self._owner = owner
        self._lease_seconds = lease_seconds
        self._max_attempts = max_attempts
        self._scan_flags = scan_flags if scan_flags is not None else dict(DEFAULT_SCAN_FLAGS)

    # -- internal helpers ----------------------------------------------------

    def _resolve_scan_callable(self) -> ScanCallable:
        if self._scan_callable is not None:
            return self._scan_callable
        # Lazy import: the real callable pulls in the scan CLI internals, which
        # we never want to pay for in the (mocked) offline test path.
        from tools.cli.wallet_scan import _default_scan_callable

        self._scan_callable = _default_scan_callable
        return self._scan_callable

    def _read_wallet_from_dossier(self, run_root: Path) -> str:
        # Reuse wallet_scan's dossier-wallet reader so the worker derives the
        # proxy wallet the same way the batch scanner does.
        from tools.cli.wallet_scan import _read_wallet_from_dossier

        return _read_wallet_from_dossier(run_root)

    # -- main loop -----------------------------------------------------------

    def run(
        self,
        *,
        max_items: int = 1,
        should_stop: Optional[Callable[[], bool]] = None,
        heartbeat: Optional[Callable[[], None]] = None,
    ) -> WorkerResult:
        """Drain up to ``max_items`` pending rows once (bounded; no scheduling).

        Order per loop, mirroring the packet contract:
            requeue_expired_leases -> get_pending -> lease -> scan ->
            dossier extract + ingest -> watchlist advance -> complete;
            on exception -> fail.

        Idempotency: a leased row is no longer pending, so a second call to
        run() (or a second worker) will not re-lease it and will not double
        scan it within the lease window.

        Cooperative shutdown (DR-0-FIX / DR-0-FIX-2): when ``should_stop`` is
        provided, the stop flag is wired into the scan HTTP retry loop
        (``tools.cli.scan.set_cancel_check``) so a stop aborts the IN-FLIGHT
        request/retry — bounding stop latency to ~one request timeout, not one
        whole wallet. The aborted wallet raises ``ScanCancelled``; it is NOT
        ingested and NOT failed (no attempt burned) — the lease is released back
        to pending so it is re-scanned cleanly later. The flag is also checked
        between wallets so no new wallet starts once stopping.

        ``heartbeat`` (manual worker) is called between wallets to refresh the
        single-host lock so a long bounded drain on the MAIN thread never lets
        the lock go stale. The scheduler refreshes from its own main control loop
        and does not pass this.
        """
        result = WorkerResult()
        scan_callable = self._resolve_scan_callable()

        # Bridge cooperative stop into the scan request/retry loop (request
        # granularity). Only the drain path passes should_stop; the foreground
        # wallet-scan path never installs this hook, so it is unaffected.
        cancel_exc: type[BaseException] = _NeverCancelled
        cancel_installed = False
        scan_mod = None
        if should_stop is not None:
            try:
                from tools.cli import scan as scan_mod  # lazy: heavy module
                scan_mod.set_cancel_check(should_stop)
                cancel_exc = scan_mod.ScanCancelled
                cancel_installed = True
            except Exception:  # pragma: no cover - defensive; degrade to between-wallet
                cancel_installed = False

        try:
            return self._run_locked(
                result,
                scan_callable,
                max_items=max_items,
                should_stop=should_stop,
                heartbeat=heartbeat,
                cancel_exc=cancel_exc,
            )
        finally:
            if cancel_installed and scan_mod is not None:
                scan_mod.clear_cancel_check()

    def _run_locked(
        self,
        result: "WorkerResult",
        scan_callable: ScanCallable,
        *,
        max_items: int,
        should_stop: Optional[Callable[[], bool]],
        heartbeat: Optional[Callable[[], None]],
        cancel_exc: type[BaseException],
    ) -> "WorkerResult":
        # Honor a stop requested before we even start: do no work.
        if should_stop is not None and should_stop():
            return result

        # Step 1: reclaim any leases whose TTL expired (counts toward attempts).
        result.requeued = self._queue.requeue_expired_leases()

        # Pull a generous candidate window; we apply our own ceiling + count.
        candidates = self._queue.get_pending(limit=max(max_items * 4, max_items))

        for row in candidates:
            if result.completed + result.failed + result.dropped >= max_items:
                break

            # Refresh the holder's lock heartbeat (manual worker) BETWEEN wallets
            # so a long bounded drain on the main thread never goes stale.
            if heartbeat is not None:
                try:
                    heartbeat()
                except Exception:  # pragma: no cover - heartbeat must never fail the drain
                    pass

            # Cooperative cancel: never START a new wallet once a stop is
            # requested. The wallet already in-flight (if any) has finished by
            # the time we loop back here.
            if should_stop is not None and should_stop():
                logger.info(
                    "scan-worker: stop requested; halting between wallets after "
                    "%d completed / %d failed (no new wallet started)",
                    result.completed,
                    result.failed,
                )
                break

            # Poison-pill ceiling: dead-letter rows that have failed too often.
            if row.attempt_count >= self._max_attempts:
                self._drop(row.dedup_key, row.attempt_count)
                result.dropped += 1
                continue

            leased = self._queue.lease(
                row.dedup_key,
                self._owner,
                lease_duration_seconds=self._lease_seconds,
            )
            if leased is None:
                # Raced away (already leased/terminal) — skip, do not double-grab.
                result.skipped += 1
                continue
            result.leased += 1

            wallet = leased.wallet_address
            try:
                run_root_str = scan_callable(wallet, self._scan_flags)
                run_root = Path(run_root_str)

                if self._post_scan_extractor is not None:
                    slug = self._read_wallet_from_dossier(run_root) or wallet
                    # DEFECT 2 (2026-06-01): dossier ingest failure is FATAL to
                    # this item. Do NOT swallow it — let it propagate to the
                    # failure path below so the item is marked failed (requeued
                    # within attempt limits) and the watchlist is NOT advanced to
                    # 'scanned'. The extractor raises on zero-persisted or any
                    # ingest error (never reports success on an empty ingest).
                    self._post_scan_extractor(run_root, str(slug), wallet)

                # Advance watchlist lifecycle to 'scanned' (WI-1 check #2) —
                # only reached after a successful dossier ingest above.
                if self._watchlist_advancer is not None:
                    try:
                        self._watchlist_advancer(wallet, run_root)
                    except Exception as exc:  # pragma: no cover - defensive
                        logger.warning(
                            "scan-worker: non-fatal watchlist advance error for %s: %s",
                            wallet,
                            exc,
                        )

                self._queue.complete(leased.dedup_key)
                result.completed += 1
                result.processed_keys.append(leased.dedup_key)
            except cancel_exc:
                # Cooperative mid-request abort (DR-0-FIX-2): an operator stop
                # interrupted the in-flight scan. This is NOT a failure — do NOT
                # ingest, do NOT advance, do NOT burn an attempt. Release the
                # lease back to pending so the wallet is re-scanned cleanly later,
                # then stop (no new wallet starts).
                self._queue.release(leased.dedup_key)
                result.cancelled += 1
                logger.info(
                    "scan-worker: in-flight scan for %s aborted on stop; lease "
                    "released to pending (not ingested, not failed)",
                    wallet,
                )
                break
            except Exception as exc:
                # LOUD by design (DEFECT 2): scan OR ingest failure fails the
                # item. The watchlist is not advanced and the row is not
                # completed; expired-lease requeue / max-attempts ceiling handle
                # retry.
                err = f"{type(exc).__name__}: {exc}"
                logger.error(
                    "scan-worker: item failed for %s: %s", wallet, err, exc_info=True
                )
                self._queue.fail(leased.dedup_key, err)
                result.failed += 1

        return result

    # -- dead-letter ---------------------------------------------------------

    def _drop(self, dedup_key: str, attempt_count: int) -> None:
        """Move a poison-pill row to the terminal 'dropped' state."""
        item = self._queue._items.get(dedup_key)  # noqa: SLF001 - same package
        if item is None:
            return
        item.queue_state = QueueState.dropped
        item.last_error = (
            f"dead-lettered: attempt_count {attempt_count} >= "
            f"max_attempts {self._max_attempts}"
        )
        item.updated_at = datetime.now(timezone.utc)
        logger.warning(
            "scan-worker: dead-lettered %s after %d attempts", dedup_key, attempt_count
        )


# ---------------------------------------------------------------------------
# Default watchlist advancer (ClickHouse-backed)
# ---------------------------------------------------------------------------


def make_clickhouse_watchlist_advancer(
    *,
    host: str = "localhost",
    port: int = 8123,
    user: str = "polytool_admin",
    password: str,
    source: str = "loop_a",
) -> WatchlistAdvancer:
    """Return a WatchlistAdvancer that writes a 'scanned' watchlist row.

    The watchlist is ReplacingMergeTree(updated_at) keyed on wallet_address, so
    writing a fresh row with lifecycle_state='scanned' and a newer updated_at
    collapses to the latest state per wallet (discovered/queued -> scanned).

    WI-4: the advance writes a CANDIDATE-tier row (tier='candidate', locked=0)
    and is GUARDED by the locked-immutability rule — if the wallet is already
    operator-locked (locked=1) in the watchlist, the advance is skipped so a
    full discovery+rescan cycle leaves the locked entry byte-identical. It still
    does NOT promote and does NOT gate on review_status (promotion still requires
    the existing human gate via validate_transition).
    """
    from packages.polymarket.discovery.clickhouse_writer import (
        read_watchlist_lock_state,
        write_watchlist_rows,
    )
    from packages.polymarket.discovery.candidate_population import (
        TIER_CANDIDATE,
        is_locked_row,
    )

    def _advance(wallet_address: str, run_root: Path) -> None:
        # WI-4 locked-immutability guard: never overwrite an operator-locked row.
        lock_state = read_watchlist_lock_state(
            wallet_address, host=host, port=port, user=user, password=password
        )
        if lock_state is not None and is_locked_row(lock_state):
            logger.info(
                "scan-worker: wallet %s is operator-locked; skipping watchlist advance "
                "(immutable per WI-4)",
                wallet_address,
            )
            return

        now = datetime.now(timezone.utc)
        run_id = run_root.name or None
        row = WatchlistRow(
            wallet_address=wallet_address,
            lifecycle_state=LifecycleState.scanned,
            review_status=ReviewStatus.pending,
            priority=3,
            source=source,
            reason="scan-worker drained scan_queue and produced a dossier",
            last_scan_run_id=run_id,
            last_scanned_at=now,
            last_activity_at=None,
            metadata_json="{}",
            updated_at=now,
            tier=TIER_CANDIDATE,
            locked=0,
        )
        ok = write_watchlist_rows(
            [row], host=host, port=port, user=user, password=password
        )
        if not ok:
            logger.error(
                "scan-worker: failed to advance watchlist for %s to 'scanned'",
                wallet_address,
            )

    return _advance
