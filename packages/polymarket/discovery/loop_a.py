"""Loop A orchestrator — leaderboard discovery for Wallet Discovery v1.

One-shot orchestrator: fetch -> churn -> enqueue.

Handles ClickHouse password via parameter. Fail-fast if not dry_run and
password is empty (CLAUDE.md ClickHouse auth rule).

SPEC: docs/specs/SPEC-wallet-discovery-v1.md section "Loop A"
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from packages.polymarket.discovery.churn_detector import ChurnResult, detect_churn
from packages.polymarket.discovery.clickhouse_writer import (
    read_latest_snapshot,
    write_leaderboard_snapshot_rows,
    write_scan_queue_rows,
    write_watchlist_rows,
)
from packages.polymarket.discovery.leaderboard_fetcher import fetch_leaderboard, to_snapshot_rows
from packages.polymarket.discovery.models import (
    LifecycleState,
    ReviewStatus,
    WatchlistRow,
)
from packages.polymarket.discovery.scan_queue import ScanQueueManager

logger = logging.getLogger(__name__)


@dataclass
class LoopAResult:
    """Result returned by run_loop_a()."""
    fetch_run_id:  str
    snapshot_ts:   datetime
    rows_fetched:  int
    churn:         ChurnResult
    rows_enqueued: int
    dry_run:       bool


def run_loop_a(
    order_by: str = "PNL",
    time_period: str = "DAY",
    category: str = "OVERALL",
    max_pages: int = 5,
    ch_host: str = "localhost",
    ch_port: int = 8123,
    ch_user: str = "polytool_admin",
    ch_password: str = "",
    dry_run: bool = False,
    http_client=None,
    # Injectable params for deterministic testing:
    fetch_run_id: Optional[str] = None,
    snapshot_ts: Optional[datetime] = None,
) -> LoopAResult:
    """Execute one Loop A discovery cycle.

    Orchestration order:
    1. Validate password (fail-fast if not dry_run and password empty)
    2. Generate fetch_run_id + snapshot_ts
    3. Fetch leaderboard entries (paginated)
    4. Read prior snapshot from ClickHouse (or empty if dry_run or first run)
    5. Detect churn (new, dropped, persisting, rising wallets)
    6. Build snapshot rows with is_new flags
    7. Write snapshots to ClickHouse (unless dry_run)
    8. Enqueue new wallets to scan_queue (unless dry_run)
    9. Update watchlist with discovered state for new wallets (unless dry_run)
    10. Return LoopAResult

    Args:
        order_by: Sort field for leaderboard fetch.
        time_period: Time period for leaderboard fetch.
        category: Category for leaderboard fetch.
        max_pages: Max pages to paginate.
        ch_host: ClickHouse host.
        ch_port: ClickHouse port.
        ch_user: ClickHouse user.
        ch_password: ClickHouse password (required if not dry_run).
        dry_run: If True, skip all ClickHouse writes.
        http_client: Injectable HttpClient for testing.
        fetch_run_id: Injectable UUID for testing (generated if None).
        snapshot_ts: Injectable timestamp for testing (generated if None).

    Returns:
        LoopAResult dataclass.

    Raises:
        ValueError: If not dry_run and ch_password is empty.
    """
    # Fail-fast password check (CLAUDE.md rule)
    if not dry_run and not ch_password:
        raise ValueError(
            "CLICKHOUSE_PASSWORD required for live Loop A run. "
            "Set ch_password or use dry_run=True."
        )

    # Generate injectable IDs
    run_id = fetch_run_id or str(uuid4())
    ts = snapshot_ts or datetime.now(timezone.utc)

    ch_kwargs = dict(host=ch_host, port=ch_port, user=ch_user, password=ch_password or "dummy")

    # Step 3: Fetch leaderboard entries
    logger.info("Loop A: fetching leaderboard order_by=%s time_period=%s category=%s max_pages=%d", order_by, time_period, category, max_pages)
    raw_entries = fetch_leaderboard(
        order_by=order_by,
        time_period=time_period,
        category=category,
        max_pages=max_pages,
        http_client=http_client,
    )
    logger.info("Loop A: fetched %d entries", len(raw_entries))

    # Step 4: Read prior snapshot (skip in dry_run to avoid CH calls)
    prior_rows = []
    if not dry_run:
        try:
            prior_rows = read_latest_snapshot(
                order_by=order_by,
                time_period=time_period,
                category=category,
                **ch_kwargs,
            )
            logger.info("Loop A: prior snapshot has %d rows", len(prior_rows))
        except Exception as exc:
            logger.warning("Loop A: could not read prior snapshot: %s — treating as first run", exc)
            prior_rows = []

    # Step 5: Detect churn
    prior_wallet_set = {r.proxy_wallet for r in prior_rows if r.proxy_wallet}
    current_snapshot_rows = to_snapshot_rows(
        raw_entries,
        run_id,
        ts,
        order_by,
        time_period,
        category,
        prior_wallets=prior_wallet_set,
    )
    churn = detect_churn(current_snapshot_rows, prior_rows)
    logger.info(
        "Loop A: churn — new=%d dropped=%d persisting=%d rising=%d",
        len(churn.new_wallets),
        len(churn.dropped_wallets),
        len(churn.persisting_wallets),
        len(churn.rising_wallets),
    )

    rows_enqueued = 0

    if not dry_run:
        # Step 7: Write snapshots to ClickHouse
        ok = write_leaderboard_snapshot_rows(current_snapshot_rows, **ch_kwargs)
        if not ok:
            logger.error("Loop A: failed to write leaderboard snapshot rows to ClickHouse")

        # Step 8: Enqueue new wallets
        if churn.new_wallets:
            queue_mgr = ScanQueueManager()
            for wallet in churn.new_wallets:
                queue_mgr.enqueue(wallet, source="loop_a", priority=3)
            rows_enqueued = len(queue_mgr._items)
            queue_rows = list(queue_mgr._items.values())
            ok = write_scan_queue_rows(queue_rows, **ch_kwargs)
            if not ok:
                logger.error("Loop A: failed to write scan queue rows to ClickHouse")

        # Step 9: Update watchlist with discovered state for new wallets
        if churn.new_wallets:
            watchlist_rows = [
                WatchlistRow(
                    wallet_address=wallet,
                    lifecycle_state=LifecycleState.discovered,
                    review_status=ReviewStatus.pending,
                    priority=3,
                    source="loop_a",
                    reason="leaderboard churn detection",
                    last_scan_run_id=None,
                    last_scanned_at=None,
                    last_activity_at=None,
                    metadata_json="{}",
                    updated_at=ts,
                )
                for wallet in churn.new_wallets
            ]
            ok = write_watchlist_rows(watchlist_rows, **ch_kwargs)
            if not ok:
                logger.error("Loop A: failed to write watchlist rows to ClickHouse")

    return LoopAResult(
        fetch_run_id=run_id,
        snapshot_ts=ts,
        rows_fetched=len(raw_entries),
        churn=churn,
        rows_enqueued=rows_enqueued,
        dry_run=dry_run,
    )
