"""Scan queue manager for Wallet Discovery v1.

In-memory implementation for testability + ClickHouse persistence methods.
Enforces one-open-item-per-dedup-key and lease/expiry semantics.

SPEC: docs/specs/SPEC-wallet-discovery-v1.md section "scan_queue table"
"""
from __future__ import annotations

import logging
from copy import copy
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

from packages.polymarket.discovery.models import QueueState, ScanQueueRow

logger = logging.getLogger(__name__)

_TERMINAL_STATES = {QueueState.done, QueueState.failed, QueueState.dropped}


class ScanQueueManager:
    """In-memory scan queue with lease/expiry semantics.

    Enforces one open item per dedup_key. A wallet can be re-queued after
    its current item reaches a terminal state (done, failed, dropped).

    Use flush_to_clickhouse() to persist state to ClickHouse.
    Use load_from_clickhouse() to hydrate state from ClickHouse.
    """

    def __init__(self) -> None:
        # _items: dedup_key -> ScanQueueRow (current item per key)
        self._items: dict[str, ScanQueueRow] = {}

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def enqueue(
        self,
        wallet_address: str,
        source: str,
        priority: int = 3,
        source_ref: str = "",
    ) -> ScanQueueRow:
        """Enqueue a wallet for scanning.

        Idempotent: if a pending or leased item already exists for this
        dedup_key, returns the existing item without creating a duplicate.

        Args:
            wallet_address: The 0x-prefixed wallet address.
            source: Source identifier ('loop_a', 'manual', 'loop_d').
            priority: 1 (highest) to 5 (lowest), default 3.
            source_ref: Optional reference string from the source.

        Returns:
            The ScanQueueRow (existing if dedup'd, new otherwise).
        """
        dedup_key = f"{source}:{wallet_address}"
        existing = self._items.get(dedup_key)

        if existing is not None and existing.queue_state not in _TERMINAL_STATES:
            # Active item exists — return it (idempotent)
            return existing

        now = self._now()
        row = ScanQueueRow(
            queue_id=str(uuid4()),
            dedup_key=dedup_key,
            wallet_address=wallet_address,
            source=source,
            source_ref=source_ref,
            priority=priority,
            queue_state=QueueState.pending,
            available_at=now,
            leased_at=None,
            lease_expires_at=None,
            lease_owner=None,
            attempt_count=0,
            last_error=None,
            created_at=now,
            updated_at=now,
        )
        self._items[dedup_key] = row
        return row

    def lease(
        self,
        dedup_key: str,
        lease_owner: str,
        lease_duration_seconds: int = 300,
    ) -> Optional[ScanQueueRow]:
        """Lease a pending item for processing.

        Args:
            dedup_key: The dedup key of the item to lease.
            lease_owner: Identifier for the consumer taking the lease.
            lease_duration_seconds: Lease TTL in seconds (default 300).

        Returns:
            The updated ScanQueueRow, or None if the item was not found or
            was not in pending state.
        """
        item = self._items.get(dedup_key)
        if item is None or item.queue_state != QueueState.pending:
            return None

        now = self._now()
        item.queue_state = QueueState.leased
        item.leased_at = now
        item.lease_expires_at = now + timedelta(seconds=lease_duration_seconds)
        item.lease_owner = lease_owner
        item.updated_at = now
        return item

    def complete(self, dedup_key: str) -> Optional[ScanQueueRow]:
        """Mark an item as successfully completed.

        Args:
            dedup_key: The dedup key of the item to complete.

        Returns:
            The updated ScanQueueRow, or None if not found.
        """
        item = self._items.get(dedup_key)
        if item is None:
            return None
        now = self._now()
        item.queue_state = QueueState.done
        item.updated_at = now
        return item

    def fail(self, dedup_key: str, error_msg: str) -> Optional[ScanQueueRow]:
        """Mark an item as failed, incrementing attempt_count.

        Args:
            dedup_key: The dedup key of the item to fail.
            error_msg: Description of the failure.

        Returns:
            The updated ScanQueueRow, or None if not found.
        """
        item = self._items.get(dedup_key)
        if item is None:
            return None
        now = self._now()
        item.queue_state = QueueState.failed
        item.last_error = error_msg
        item.attempt_count += 1
        item.updated_at = now
        return item

    def get_pending(self, limit: int = 10) -> list[ScanQueueRow]:
        """Return pending items available for processing.

        Filters: queue_state='pending' AND available_at <= now().
        Orders: priority ASC, then created_at ASC.

        Args:
            limit: Maximum number of items to return.

        Returns:
            List of pending ScanQueueRow objects.
        """
        now = self._now()
        pending = [
            item
            for item in self._items.values()
            if item.queue_state == QueueState.pending and item.available_at <= now
        ]
        pending.sort(key=lambda r: (r.priority, r.created_at))
        return pending[:limit]

    def requeue_expired_leases(self) -> int:
        """Find leased items past lease_expires_at and reset to pending.

        Increments attempt_count on each re-queued item.

        Returns:
            Number of items re-queued.
        """
        now = self._now()
        count = 0
        for item in self._items.values():
            if (
                item.queue_state == QueueState.leased
                and item.lease_expires_at is not None
                and item.lease_expires_at < now
            ):
                item.queue_state = QueueState.pending
                item.leased_at = None
                item.lease_expires_at = None
                item.lease_owner = None
                item.attempt_count += 1
                item.updated_at = now
                count += 1
        return count

    def flush_to_clickhouse(
        self,
        *,
        host: str = "localhost",
        port: int = 8123,
        user: str = "polytool_admin",
        password: str,
    ) -> bool:
        """Persist all in-memory items to ClickHouse.

        Returns True if all writes succeeded.
        """
        from packages.polymarket.discovery.clickhouse_writer import write_scan_queue_rows
        rows = list(self._items.values())
        return write_scan_queue_rows(rows, host=host, port=port, user=user, password=password)

    def load_from_clickhouse(
        self,
        *,
        host: str = "localhost",
        port: int = 8123,
        user: str = "polytool_admin",
        password: str,
    ) -> int:
        """Hydrate in-memory state from ClickHouse scan_queue table.

        Returns number of rows loaded.
        """
        import base64
        import json
        import urllib.parse
        import urllib.request
        from packages.polymarket.discovery.models import QueueState as QS

        if not password:
            raise ValueError("CLICKHOUSE_PASSWORD required.")

        sql = (
            "SELECT queue_id, dedup_key, wallet_address, source, source_ref, "
            "priority, queue_state, available_at, leased_at, lease_expires_at, "
            "lease_owner, attempt_count, last_error, created_at, updated_at "
            "FROM polytool.scan_queue "
            "ORDER BY dedup_key FORMAT JSONEachRow"
        )
        url = f"http://{host}:{port}/?query={urllib.parse.quote(sql)}"
        credentials = base64.b64encode(f"{user}:{password}".encode()).decode()
        req = urllib.request.Request(
            url,
            headers={"Authorization": f"Basic {credentials}"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read().decode("utf-8")
        except Exception as exc:
            logger.error("load_from_clickhouse failed: %s", exc)
            return 0

        count = 0
        for line in raw.strip().splitlines():
            if not line.strip():
                continue
            try:
                d = json.loads(line)
                from datetime import datetime as DT

                def _parse_dt(s):
                    if not s:
                        return None
                    return DT.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)

                row = ScanQueueRow(
                    queue_id=d["queue_id"],
                    dedup_key=d["dedup_key"],
                    wallet_address=d["wallet_address"],
                    source=d["source"],
                    source_ref=d.get("source_ref", ""),
                    priority=int(d.get("priority", 3)),
                    queue_state=QS(d["queue_state"]),
                    available_at=_parse_dt(d["available_at"]) or datetime.now(timezone.utc),
                    leased_at=_parse_dt(d.get("leased_at")),
                    lease_expires_at=_parse_dt(d.get("lease_expires_at")),
                    lease_owner=d.get("lease_owner"),
                    attempt_count=int(d.get("attempt_count", 0)),
                    last_error=d.get("last_error"),
                    created_at=_parse_dt(d["created_at"]) or datetime.now(timezone.utc),
                    updated_at=_parse_dt(d["updated_at"]) or datetime.now(timezone.utc),
                )
                self._items[row.dedup_key] = row
                count += 1
            except Exception as exc:
                logger.warning("Skipping malformed scan_queue row: %s", exc)

        return count
