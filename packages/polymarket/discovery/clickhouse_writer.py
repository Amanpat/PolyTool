"""ClickHouse HTTP interface for Wallet Discovery v1 tables.

All ClickHouse I/O is in this module. The models, lifecycle logic, and fetcher
are pure Python with no ClickHouse dependency, enabling deterministic testing.

Pattern: urllib.request + Basic auth + JSONEachRow format.
Follows silver_tape_metadata.py convention (not clickhouse_connect).

CLAUDE.md rule: password parameter required; raise ValueError if empty.
Never hardcode. Only localhost HTTP (no remote).
"""
from __future__ import annotations

import base64
import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Optional

from packages.polymarket.discovery.models import (
    LeaderboardSnapshotRow,
    ScanQueueRow,
    WatchlistRow,
)


def _require_password(password: str) -> None:
    """Enforce fail-fast password check per CLAUDE.md ClickHouse auth rule."""
    if not password:
        raise ValueError(
            "CLICKHOUSE_PASSWORD required. Set the CLICKHOUSE_PASSWORD environment "
            "variable and pass it via the --clickhouse-password flag or ch_password "
            "parameter. Never hardcode credentials."
        )


def _dt_to_ch(dt: Optional[datetime]) -> Optional[str]:
    """Convert datetime to ClickHouse-compatible ISO string (no timezone offset)."""
    if dt is None:
        return None
    # ClickHouse DateTime expects 'YYYY-MM-DD HH:MM:SS' format
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _post_jsonl(
    ndjson: str,
    *,
    table: str,
    host: str,
    port: int,
    user: str,
    password: str,
) -> bool:
    """POST NDJSON rows to a ClickHouse table via HTTP. Returns True on success."""
    try:
        query = f"INSERT INTO polytool.{table} FORMAT JSONEachRow"
        url = f"http://{host}:{port}/?query={urllib.parse.quote(query)}"
        data = ndjson.encode("utf-8")
        credentials = base64.b64encode(f"{user}:{password}".encode()).decode()
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Basic {credentials}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception:
        return False


def _get_query(
    sql: str,
    *,
    host: str,
    port: int,
    user: str,
    password: str,
) -> Optional[str]:
    """Execute a SELECT query via ClickHouse HTTP GET. Returns response text or None."""
    try:
        full_sql = sql + " FORMAT JSONEachRow"
        url = f"http://{host}:{port}/?query={urllib.parse.quote(full_sql)}"
        credentials = base64.b64encode(f"{user}:{password}".encode()).decode()
        req = urllib.request.Request(
            url,
            headers={"Authorization": f"Basic {credentials}"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.read().decode("utf-8")
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Write functions
# ---------------------------------------------------------------------------

def write_watchlist_rows(
    rows: list[WatchlistRow],
    *,
    host: str = "localhost",
    port: int = 8123,
    user: str = "polytool_admin",
    password: str,
) -> bool:
    """Insert WatchlistRow objects into polytool.watchlist. Returns True on success."""
    _require_password(password)
    if not rows:
        return True
    lines = []
    for row in rows:
        d = {
            "wallet_address":   row.wallet_address,
            "lifecycle_state":  row.lifecycle_state.value if hasattr(row.lifecycle_state, "value") else row.lifecycle_state,
            "review_status":    row.review_status.value if hasattr(row.review_status, "value") else row.review_status,
            "priority":         row.priority,
            "source":           row.source,
            "reason":           row.reason,
            "metadata_json":    row.metadata_json,
            "updated_at":       _dt_to_ch(row.updated_at),
        }
        if row.last_scan_run_id is not None:
            d["last_scan_run_id"] = row.last_scan_run_id
        if row.last_scanned_at is not None:
            d["last_scanned_at"] = _dt_to_ch(row.last_scanned_at)
        if row.last_activity_at is not None:
            d["last_activity_at"] = _dt_to_ch(row.last_activity_at)
        lines.append(json.dumps(d))
    return _post_jsonl("\n".join(lines), table="watchlist", host=host, port=port, user=user, password=password)


def write_leaderboard_snapshot_rows(
    rows: list[LeaderboardSnapshotRow],
    *,
    host: str = "localhost",
    port: int = 8123,
    user: str = "polytool_admin",
    password: str,
) -> bool:
    """Insert LeaderboardSnapshotRow objects into polytool.leaderboard_snapshots."""
    _require_password(password)
    if not rows:
        return True
    lines = []
    for row in rows:
        d = {
            "snapshot_ts":      _dt_to_ch(row.snapshot_ts),
            "fetch_run_id":     row.fetch_run_id,
            "order_by":         row.order_by,
            "time_period":      row.time_period,
            "category":         row.category,
            "rank":             row.rank,
            "proxy_wallet":     row.proxy_wallet,
            "username":         row.username,
            "pnl":              row.pnl,
            "volume":           row.volume,
            "is_new":           row.is_new,
            "raw_payload_json": row.raw_payload_json,
        }
        lines.append(json.dumps(d))
    return _post_jsonl("\n".join(lines), table="leaderboard_snapshots", host=host, port=port, user=user, password=password)


def write_scan_queue_rows(
    rows: list[ScanQueueRow],
    *,
    host: str = "localhost",
    port: int = 8123,
    user: str = "polytool_admin",
    password: str,
) -> bool:
    """Insert ScanQueueRow objects into polytool.scan_queue."""
    _require_password(password)
    if not rows:
        return True
    lines = []
    for row in rows:
        d = {
            "queue_id":         row.queue_id,
            "dedup_key":        row.dedup_key,
            "wallet_address":   row.wallet_address,
            "source":           row.source,
            "source_ref":       row.source_ref,
            "priority":         row.priority,
            "queue_state":      row.queue_state.value if hasattr(row.queue_state, "value") else row.queue_state,
            "available_at":     _dt_to_ch(row.available_at),
            "attempt_count":    row.attempt_count,
            "created_at":       _dt_to_ch(row.created_at),
            "updated_at":       _dt_to_ch(row.updated_at),
        }
        if row.leased_at is not None:
            d["leased_at"] = _dt_to_ch(row.leased_at)
        if row.lease_expires_at is not None:
            d["lease_expires_at"] = _dt_to_ch(row.lease_expires_at)
        if row.lease_owner is not None:
            d["lease_owner"] = row.lease_owner
        if row.last_error is not None:
            d["last_error"] = row.last_error
        lines.append(json.dumps(d))
    return _post_jsonl("\n".join(lines), table="scan_queue", host=host, port=port, user=user, password=password)


# ---------------------------------------------------------------------------
# Read function
# ---------------------------------------------------------------------------

def read_latest_snapshot(
    order_by: str,
    time_period: str,
    category: str,
    *,
    host: str = "localhost",
    port: int = 8123,
    user: str = "polytool_admin",
    password: str,
) -> list[LeaderboardSnapshotRow]:
    """Query leaderboard_snapshots for the most recent snapshot at the given key.

    Returns list of LeaderboardSnapshotRow for the latest snapshot_ts at
    (order_by, time_period, category). Returns empty list if no rows or on error.
    """
    _require_password(password)
    sql = f"""
SELECT
    snapshot_ts,
    fetch_run_id,
    order_by,
    time_period,
    category,
    rank,
    proxy_wallet,
    username,
    pnl,
    volume,
    is_new,
    raw_payload_json
FROM polytool.leaderboard_snapshots
WHERE order_by = '{order_by}'
  AND time_period = '{time_period}'
  AND category = '{category}'
  AND snapshot_ts = (
      SELECT max(snapshot_ts)
      FROM polytool.leaderboard_snapshots
      WHERE order_by = '{order_by}'
        AND time_period = '{time_period}'
        AND category = '{category}'
  )
ORDER BY rank ASC
""".strip()

    raw = _get_query(sql, host=host, port=port, user=user, password=password)
    if not raw or not raw.strip():
        return []

    rows: list[LeaderboardSnapshotRow] = []
    for line in raw.strip().splitlines():
        if not line.strip():
            continue
        try:
            d = json.loads(line)
            rows.append(
                LeaderboardSnapshotRow(
                    snapshot_ts=datetime.strptime(d["snapshot_ts"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc),
                    fetch_run_id=d["fetch_run_id"],
                    order_by=d["order_by"],
                    time_period=d["time_period"],
                    category=d["category"],
                    rank=int(d["rank"]),
                    proxy_wallet=d["proxy_wallet"],
                    username=d.get("username", ""),
                    pnl=float(d["pnl"]),
                    volume=float(d["volume"]),
                    is_new=int(d.get("is_new", 0)),
                    raw_payload_json=d.get("raw_payload_json", "{}"),
                )
            )
        except Exception:
            continue
    return rows
