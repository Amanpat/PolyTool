"""2-minute price history fetcher and ClickHouse ingest for polytool.price_2min.

Architecture (v4.2):
    price_2min  = live-updating ClickHouse table; written by this module
    price_history_2min = legacy bulk-import table from local files (packages/polymarket/historical_import/)

These are distinct use cases. This module fetches from the CLOB API directly.

Usage:
    from packages.polymarket.price_2min_fetcher import FetchAndIngestEngine, FetchConfig

    engine = FetchAndIngestEngine(config)
    result = engine.run(token_ids=["0xabc..."], dry_run=False)
"""

from __future__ import annotations

import logging
import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Protocol

logger = logging.getLogger(__name__)

# ClickHouse table written by this module (v4.2 canonical live series)
_TABLE = "polytool.price_2min"
_COLUMNS = ["token_id", "ts", "price", "source", "import_run_id"]
_SOURCE_TAG = "clob_api"

# Default CLOB endpoint
DEFAULT_CLOB_BASE = "https://clob.polymarket.com"
# Fidelity=2 means 2-minute buckets; interval=max fetches full history
_FIDELITY = 2
_INTERVAL = "max"


# ---------------------------------------------------------------------------
# Row normalization
# ---------------------------------------------------------------------------


def _to_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        f = float(value)
        return f if math.isfinite(f) else default
    except (TypeError, ValueError):
        return default


def _to_utc_datetime(value: Any) -> Optional[datetime]:
    """Convert API timestamp (epoch seconds int/float or ISO str) to UTC datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        if not math.isfinite(value):
            return None
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        # Try numeric epoch
        try:
            epoch = float(text)
            if math.isfinite(epoch):
                return datetime.fromtimestamp(epoch, tz=timezone.utc)
        except ValueError:
            pass
        # Try ISO format
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(text)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            return None
    return None


def normalize_rows(
    token_id: str,
    raw_history: List[Dict[str, Any]],
    run_id: str,
) -> List[list]:
    """Normalize raw CLOB /prices-history response rows into CH insert rows.

    Each input record is expected to have:
        "t": epoch seconds (int or float)
        "p": price (float or string)

    Rows with unparseable timestamps are silently skipped.

    Returns:
        List of [token_id, ts, price, source, import_run_id] lists.
    """
    rows: List[list] = []
    for record in raw_history:
        if not isinstance(record, dict):
            continue
        ts = _to_utc_datetime(record.get("t"))
        if ts is None:
            continue
        price = _to_float(record.get("p"), 0.0)
        rows.append([token_id, ts, price, _SOURCE_TAG, run_id])
    return rows


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class TokenFetchResult:
    """Per-token fetch + ingest outcome."""

    token_id: str
    rows_fetched: int = 0
    rows_inserted: int = 0
    rows_skipped: int = 0
    error: Optional[str] = None


@dataclass
class FetchResult:
    """Aggregate result for a fetch-price-2min run."""

    run_id: str
    import_mode: str  # "dry-run" or "live"
    destination_table: str = _TABLE
    tokens: List[TokenFetchResult] = field(default_factory=list)
    total_rows_fetched: int = 0
    total_rows_inserted: int = 0
    total_rows_skipped: int = 0
    errors: List[str] = field(default_factory=list)
    started_at: str = ""
    completed_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "import_mode": self.import_mode,
            "destination_table": self.destination_table,
            "tokens": [
                {
                    "token_id": t.token_id,
                    "rows_fetched": t.rows_fetched,
                    "rows_inserted": t.rows_inserted,
                    "rows_skipped": t.rows_skipped,
                    "error": t.error,
                }
                for t in self.tokens
            ],
            "total_rows_fetched": self.total_rows_fetched,
            "total_rows_inserted": self.total_rows_inserted,
            "total_rows_skipped": self.total_rows_skipped,
            "errors": self.errors,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


# ---------------------------------------------------------------------------
# Protocol for injectable dependencies
# ---------------------------------------------------------------------------


class CHInsertClient(Protocol):
    def insert_rows(self, table: str, column_names: List[str], rows: List[list]) -> int:
        ...


FetchFn = Callable[[str], List[Dict[str, Any]]]
"""Type alias: callable(token_id) -> list of {t, p} dicts."""


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class FetchConfig:
    clob_base_url: str = DEFAULT_CLOB_BASE
    fidelity: int = _FIDELITY
    interval: str = _INTERVAL
    clickhouse_host: str = "localhost"
    clickhouse_port: int = 8123
    clickhouse_user: str = "polytool_admin"
    clickhouse_password: str = ""


class FetchAndIngestEngine:
    """Fetch 2-min price history from CLOB API and ingest into polytool.price_2min.

    Injectable dependencies allow fully offline testing:
        _fetch_fn: callable(token_id) -> raw history list (default: real ClobClient call)
        _ch_client: CHInsertClient (default: real ClickHouseClient from importer)

    Args:
        config: FetchConfig for API + CH connection settings.
        _fetch_fn: Optional override for the HTTP fetch (for testing).
        _ch_client: Optional override for the CH insert client (for testing).
    """

    def __init__(
        self,
        config: Optional[FetchConfig] = None,
        *,
        _fetch_fn: Optional[FetchFn] = None,
        _ch_client: Optional[Any] = None,
    ) -> None:
        self._config = config or FetchConfig()
        self._fetch_fn = _fetch_fn
        self._ch_client = _ch_client

    def _get_fetch_fn(self) -> FetchFn:
        if self._fetch_fn is not None:
            return self._fetch_fn

        from packages.polymarket.clob import ClobClient

        clob = ClobClient(base_url=self._config.clob_base_url)

        def _real_fetch(token_id: str) -> List[Dict[str, Any]]:
            resp = clob.get_prices_history(
                token_id,
                interval=self._config.interval,
                fidelity=self._config.fidelity,
            )
            return resp.get("history") or []

        return _real_fetch

    def _get_ch_client(self) -> Any:
        if self._ch_client is not None:
            return self._ch_client

        from packages.polymarket.historical_import.importer import ClickHouseClient

        return ClickHouseClient(
            host=self._config.clickhouse_host,
            port=self._config.clickhouse_port,
            user=self._config.clickhouse_user,
            password=self._config.clickhouse_password,
        )

    def run(
        self,
        token_ids: List[str],
        *,
        dry_run: bool = True,
        run_id: Optional[str] = None,
    ) -> FetchResult:
        """Fetch and ingest 2-minute price history for the given token IDs.

        Args:
            token_ids: List of Polymarket CLOB token IDs.
            dry_run: When True, normalize rows but do not write to ClickHouse.
            run_id: Optional run identifier. Auto-generated UUID if None.

        Returns:
            FetchResult with per-token outcomes and aggregate counts.
        """
        if run_id is None:
            run_id = str(uuid.uuid4())

        result = FetchResult(
            run_id=run_id,
            import_mode="dry-run" if dry_run else "live",
            started_at=_utcnow_iso(),
        )

        fetch_fn = self._get_fetch_fn()
        ch_client = None if dry_run else self._get_ch_client()

        for token_id in token_ids:
            token_result = TokenFetchResult(token_id=token_id)
            try:
                raw = fetch_fn(token_id)
                rows = normalize_rows(token_id, raw, run_id)
                token_result.rows_fetched = len(raw)
                token_result.rows_skipped = len(raw) - len(rows)

                if rows and not dry_run:
                    inserted = ch_client.insert_rows(_TABLE, _COLUMNS, rows)
                    token_result.rows_inserted = inserted
                elif rows and dry_run:
                    token_result.rows_inserted = 0  # would-be inserts, not committed

            except Exception as exc:
                msg = f"{token_id}: {exc}"
                token_result.error = msg
                result.errors.append(msg)
                logger.warning("fetch_price_2min error: %s", msg)

            result.tokens.append(token_result)
            result.total_rows_fetched += token_result.rows_fetched
            result.total_rows_inserted += token_result.rows_inserted
            result.total_rows_skipped += token_result.rows_skipped

        result.completed_at = _utcnow_iso()
        return result
