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


@dataclass
class WorkerResult:
    """Summary of one bounded worker drain."""

    requeued: int = 0
    leased: int = 0
    completed: int = 0
    failed: int = 0
    dropped: int = 0
    skipped: int = 0
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

    def run(self, *, max_items: int = 1) -> WorkerResult:
        """Drain up to ``max_items`` pending rows once (bounded; no scheduling).

        Order per loop, mirroring the packet contract:
            requeue_expired_leases -> get_pending -> lease -> scan ->
            dossier extract + ingest -> watchlist advance -> complete;
            on exception -> fail.

        Idempotency: a leased row is no longer pending, so a second call to
        run() (or a second worker) will not re-lease it and will not double
        scan it within the lease window.
        """
        result = WorkerResult()
        scan_callable = self._resolve_scan_callable()

        # Step 1: reclaim any leases whose TTL expired (counts toward attempts).
        result.requeued = self._queue.requeue_expired_leases()

        # Pull a generous candidate window; we apply our own ceiling + count.
        candidates = self._queue.get_pending(limit=max(max_items * 4, max_items))

        for row in candidates:
            if result.completed + result.failed + result.dropped >= max_items:
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
                    # Non-fatal by contract; the extractor itself swallows its
                    # own errors, but guard here too so ingestion failure does
                    # not flip a successful scan into a queue failure.
                    try:
                        self._post_scan_extractor(run_root, str(slug), wallet)
                    except Exception as exc:  # pragma: no cover - defensive
                        logger.warning(
                            "scan-worker: non-fatal dossier extract error for %s: %s",
                            wallet,
                            exc,
                        )

                # Advance watchlist lifecycle to 'scanned' (WI-1 check #2).
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
            except Exception as exc:
                err = f"{type(exc).__name__}: {exc}"
                logger.warning("scan-worker: scan failed for %s: %s", wallet, err)
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

    This stays inside WI-1 scope: it records that the wallet was scanned. It
    does NOT set tiers, locks, or promote (that is WP-4), and it does not gate
    on review_status (promotion still requires the existing human gate).
    """
    from packages.polymarket.discovery.clickhouse_writer import write_watchlist_rows

    def _advance(wallet_address: str, run_root: Path) -> None:
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
