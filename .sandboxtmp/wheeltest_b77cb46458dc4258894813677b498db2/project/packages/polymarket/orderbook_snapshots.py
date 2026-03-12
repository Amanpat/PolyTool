"""Orderbook snapshot computation for liquidity tracking.

Captures point-in-time liquidity metrics from the CLOB orderbook:
- Best bid/ask and spread
- Depth within configurable bps band
- Slippage estimates for configurable notional sizes
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Literal
import logging

from .clob import ClobClient
from .slippage import estimate_slippage_bps
import requests

logger = logging.getLogger(__name__)

SnapshotStatus = Literal["ok", "empty", "one_sided", "no_orderbook", "error"]

# Default configuration - can be overridden via function params
DEFAULT_DEPTH_BAND_BPS = 50
DEFAULT_NOTIONALS = [100, 500]  # USD notional sizes for slippage


@dataclass
class OrderbookSnapshot:
    """Point-in-time orderbook metrics for a token."""

    token_id: str
    snapshot_ts: datetime
    best_bid: Optional[float]
    best_ask: Optional[float]
    mid_price: Optional[float]
    spread_bps: Optional[float]
    depth_bid_usd_50bps: Optional[float]
    depth_ask_usd_50bps: Optional[float]
    slippage_buy_bps_100: Optional[float]
    slippage_sell_bps_100: Optional[float]
    slippage_buy_bps_500: Optional[float]
    slippage_sell_bps_500: Optional[float]
    levels_captured: int
    book_timestamp: Optional[str]
    status: SnapshotStatus
    reason: Optional[str]
    source: str = "api_snapshot"

    def to_row(self) -> list:
        """Convert to ClickHouse row format."""
        return [
            self.token_id,
            self.snapshot_ts,
            self.best_bid,
            self.best_ask,
            self.mid_price,
            self.spread_bps,
            self.depth_bid_usd_50bps,
            self.depth_ask_usd_50bps,
            self.slippage_buy_bps_100,
            self.slippage_sell_bps_100,
            self.slippage_buy_bps_500,
            self.slippage_sell_bps_500,
            self.levels_captured,
            self.book_timestamp,
            self.status,
            self.reason,
            self.source,
            datetime.utcnow(),
        ]


@dataclass
class SnapshotBatchResult:
    """Result of batch snapshot operation."""

    snapshots: list[OrderbookSnapshot] = field(default_factory=list)
    tokens_attempted: int = 0
    tokens_ok: int = 0
    tokens_empty: int = 0
    tokens_one_sided: int = 0
    tokens_no_orderbook: int = 0
    tokens_error: int = 0
    tokens_http_429: int = 0
    tokens_http_5xx: int = 0
    tokens_skipped_limit: list[str] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)


def _extract_level_price(level: object) -> Optional[float]:
    """Extract price from an orderbook level."""
    if isinstance(level, dict):
        price = level.get("price") or level.get("p")
    elif isinstance(level, (list, tuple)) and level:
        price = level[0]
    else:
        return None

    try:
        return float(price)
    except (TypeError, ValueError):
        return None


def _extract_level_size(level: object) -> Optional[float]:
    """Extract size from an orderbook level."""
    if isinstance(level, dict):
        size = level.get("size") or level.get("s")
    elif isinstance(level, (list, tuple)) and len(level) > 1:
        size = level[1]
    else:
        return None

    try:
        return float(size)
    except (TypeError, ValueError):
        return None


def _extract_error_message_from_response(response: requests.Response) -> Optional[str]:
    try:
        payload = response.json()
    except ValueError:
        text = response.text.strip()
        return text or None

    if isinstance(payload, dict):
        for key in ("error", "message", "detail"):
            value = payload.get(key)
            if value:
                return str(value)
    if isinstance(payload, str):
        return payload
    return None


def _build_basic_snapshot(
    token_id: str,
    snapshot_ts: datetime,
    status: SnapshotStatus,
    reason: Optional[str],
) -> OrderbookSnapshot:
    return OrderbookSnapshot(
        token_id=token_id,
        snapshot_ts=snapshot_ts,
        best_bid=None,
        best_ask=None,
        mid_price=None,
        spread_bps=None,
        depth_bid_usd_50bps=None,
        depth_ask_usd_50bps=None,
        slippage_buy_bps_100=None,
        slippage_sell_bps_100=None,
        slippage_buy_bps_500=None,
        slippage_sell_bps_500=None,
        levels_captured=0,
        book_timestamp=None,
        status=status,
        reason=reason,
    )


def _compute_depth_within_band(
    levels: list,
    mid_price: float,
    band_bps: float,
    side: str,
) -> float:
    """
    Compute total USD depth within band_bps of mid_price.

    For bids: sum size * price where price >= mid * (1 - band_bps/10000)
    For asks: sum size * price where price <= mid * (1 + band_bps/10000)

    Args:
        levels: List of orderbook levels
        mid_price: Mid price (best_bid + best_ask) / 2
        band_bps: Band in basis points (e.g., 50 for 0.5%)
        side: "bid" or "ask"

    Returns:
        Total USD depth within the band
    """
    if not levels or mid_price <= 0:
        return 0.0

    band_factor = band_bps / 10000.0
    total_depth_usd = 0.0

    for level in levels:
        price = _extract_level_price(level)
        size = _extract_level_size(level)
        if price is None or size is None or price <= 0:
            continue

        if side == "bid":
            # Bids within band: price >= mid * (1 - band)
            if price >= mid_price * (1 - band_factor):
                total_depth_usd += size * price
        else:
            # Asks within band: price <= mid * (1 + band)
            if price <= mid_price * (1 + band_factor):
                total_depth_usd += size * price

    return round(total_depth_usd, 2)


def _compute_slippage_for_notional(
    book: dict,
    side: str,
    notional_usd: float,
    mid_price: float,
) -> Optional[float]:
    """
    Compute slippage bps for a given notional USD amount.

    Converts notional to shares using mid price, then uses estimate_slippage_bps.

    Args:
        book: Orderbook dict with 'bids' and 'asks'
        side: 'BUY' or 'SELL'
        notional_usd: Notional amount in USD
        mid_price: Mid price for conversion

    Returns:
        Slippage in basis points, or None if cannot compute
    """
    if mid_price <= 0:
        return None

    # Convert notional to shares: shares = notional / price
    shares = notional_usd / mid_price

    result = estimate_slippage_bps(book, side, shares)
    return result.slippage_bps


def snapshot_from_book(
    token_id: str,
    book: object,
    snapshot_ts: datetime,
    depth_band_bps: float = DEFAULT_DEPTH_BAND_BPS,
    notional_sizes: Optional[list[float]] = None,
) -> OrderbookSnapshot:
    if notional_sizes is None:
        notional_sizes = DEFAULT_NOTIONALS

    if not isinstance(book, dict):
        return _build_basic_snapshot(
            token_id=token_id,
            snapshot_ts=snapshot_ts,
            status="error",
            reason="Invalid orderbook payload",
        )

    bids = book.get("bids") or []
    asks = book.get("asks") or []

    book_timestamp = book.get("timestamp") or book.get("ts")
    if book_timestamp is not None:
        book_timestamp = str(book_timestamp)

    levels_captured = len(bids) + len(asks)

    if not bids and not asks:
        return OrderbookSnapshot(
            token_id=token_id,
            snapshot_ts=snapshot_ts,
            best_bid=None,
            best_ask=None,
            mid_price=None,
            spread_bps=None,
            depth_bid_usd_50bps=None,
            depth_ask_usd_50bps=None,
            slippage_buy_bps_100=None,
            slippage_sell_bps_100=None,
            slippage_buy_bps_500=None,
            slippage_sell_bps_500=None,
            levels_captured=0,
            book_timestamp=book_timestamp,
            status="empty",
            reason="Empty orderbook",
        )

    best_bid = _extract_level_price(bids[0]) if bids else None
    best_ask = _extract_level_price(asks[0]) if asks else None

    if best_bid is None or best_ask is None:
        return OrderbookSnapshot(
            token_id=token_id,
            snapshot_ts=snapshot_ts,
            best_bid=best_bid,
            best_ask=best_ask,
            mid_price=None,
            spread_bps=None,
            depth_bid_usd_50bps=_compute_depth_within_band(
                bids,
                best_bid or 0.5,
                depth_band_bps,
                "bid",
            ) if best_bid else None,
            depth_ask_usd_50bps=_compute_depth_within_band(
                asks,
                best_ask or 0.5,
                depth_band_bps,
                "ask",
            ) if best_ask else None,
            slippage_buy_bps_100=None,
            slippage_sell_bps_100=None,
            slippage_buy_bps_500=None,
            slippage_sell_bps_500=None,
            levels_captured=levels_captured,
            book_timestamp=book_timestamp,
            status="one_sided",
            reason="One-sided orderbook" + (" (no bids)" if best_bid is None else " (no asks)"),
        )

    mid_price = (best_bid + best_ask) / 2.0
    spread_bps = ((best_ask - best_bid) / mid_price) * 10000 if mid_price > 0 else None

    depth_bid_usd = _compute_depth_within_band(bids, mid_price, depth_band_bps, "bid")
    depth_ask_usd = _compute_depth_within_band(asks, mid_price, depth_band_bps, "ask")

    slippage_buy_100 = None
    slippage_sell_100 = None
    slippage_buy_500 = None
    slippage_sell_500 = None

    if 100 in notional_sizes or len(notional_sizes) >= 1:
        notional = 100 if 100 in notional_sizes else notional_sizes[0]
        slippage_buy_100 = _compute_slippage_for_notional(book, "BUY", notional, mid_price)
        slippage_sell_100 = _compute_slippage_for_notional(book, "SELL", notional, mid_price)

    if 500 in notional_sizes or len(notional_sizes) >= 2:
        notional = 500 if 500 in notional_sizes else notional_sizes[1] if len(notional_sizes) >= 2 else 500
        slippage_buy_500 = _compute_slippage_for_notional(book, "BUY", notional, mid_price)
        slippage_sell_500 = _compute_slippage_for_notional(book, "SELL", notional, mid_price)

    return OrderbookSnapshot(
        token_id=token_id,
        snapshot_ts=snapshot_ts,
        best_bid=round(best_bid, 6),
        best_ask=round(best_ask, 6),
        mid_price=round(mid_price, 6),
        spread_bps=round(spread_bps, 2) if spread_bps is not None else None,
        depth_bid_usd_50bps=depth_bid_usd,
        depth_ask_usd_50bps=depth_ask_usd,
        slippage_buy_bps_100=slippage_buy_100,
        slippage_sell_bps_100=slippage_sell_100,
        slippage_buy_bps_500=slippage_buy_500,
        slippage_sell_bps_500=slippage_sell_500,
        levels_captured=levels_captured,
        book_timestamp=book_timestamp,
        status="ok",
        reason=None,
    )


def snapshot_token_book(
    token_id: str,
    clob_client: ClobClient,
    snapshot_ts: Optional[datetime] = None,
    depth_band_bps: float = DEFAULT_DEPTH_BAND_BPS,
    notional_sizes: Optional[list[float]] = None,
) -> OrderbookSnapshot:
    """
    Capture a snapshot of orderbook metrics for a single token.

    Fetches the orderbook and computes:
    - Best bid/ask and spread
    - Depth within band_bps of mid
    - Slippage for each notional size

    Args:
        token_id: Token ID to snapshot
        clob_client: CLOB API client
        snapshot_ts: Timestamp for snapshot (defaults to now)
        depth_band_bps: Band for depth calculation (default 50bps)
        notional_sizes: List of notional USD sizes for slippage (default [100, 500])

    Returns:
        OrderbookSnapshot with computed metrics
    """
    if snapshot_ts is None:
        snapshot_ts = datetime.utcnow()

    if notional_sizes is None:
        notional_sizes = DEFAULT_NOTIONALS

    try:
        book = clob_client.fetch_book(token_id)
    except Exception as exc:
        logger.warning(f"Failed to fetch orderbook for {token_id}: {exc}")
        status: SnapshotStatus = "error"
        reason = str(exc)
        response = getattr(exc, "response", None)
        if response is not None:
            status_code = response.status_code
            error_message = _extract_error_message_from_response(response)
            if status_code == 404 and error_message and "No orderbook exists" in error_message:
                status = "no_orderbook"
                reason = error_message
            else:
                if status_code == 429:
                    reason = error_message or "HTTP 429"
                elif 500 <= status_code <= 599:
                    reason = error_message or f"HTTP {status_code}"
                else:
                    reason = error_message or f"HTTP {status_code}"

        return _build_basic_snapshot(
            token_id=token_id,
            snapshot_ts=snapshot_ts,
            status=status,
            reason=reason,
        )

    return snapshot_from_book(
        token_id=token_id,
        book=book,
        snapshot_ts=snapshot_ts,
        depth_band_bps=depth_band_bps,
        notional_sizes=notional_sizes,
    )


def snapshot_tokens(
    token_ids: list[str],
    clob_client: ClobClient,
    max_tokens: int = 200,
    depth_band_bps: float = DEFAULT_DEPTH_BAND_BPS,
    notional_sizes: Optional[list[float]] = None,
) -> SnapshotBatchResult:
    """
    Snapshot multiple tokens with rate limiting and error handling.

    Args:
        token_ids: List of token IDs to snapshot
        clob_client: CLOB API client
        max_tokens: Maximum tokens to process (default 200)
        depth_band_bps: Band for depth calculation (default 50bps)
        notional_sizes: List of notional USD sizes for slippage

    Returns:
        SnapshotBatchResult with all snapshots and statistics
    """
    if notional_sizes is None:
        notional_sizes = DEFAULT_NOTIONALS

    result = SnapshotBatchResult()
    snapshot_ts = datetime.utcnow()

    # Deduplicate and limit
    unique_tokens = list(dict.fromkeys(token_ids))  # Preserve order, remove dupes
    tokens_to_process = unique_tokens[:max_tokens]
    result.tokens_skipped_limit = unique_tokens[max_tokens:]

    result.tokens_attempted = len(tokens_to_process)

    for token_id in tokens_to_process:
        try:
            snapshot = snapshot_token_book(
                token_id=token_id,
                clob_client=clob_client,
                snapshot_ts=snapshot_ts,
                depth_band_bps=depth_band_bps,
                notional_sizes=notional_sizes,
            )
            result.snapshots.append(snapshot)

            if snapshot.status == "ok":
                result.tokens_ok += 1
            elif snapshot.status == "empty":
                result.tokens_empty += 1
            elif snapshot.status == "one_sided":
                result.tokens_one_sided += 1
            elif snapshot.status == "no_orderbook":
                result.tokens_no_orderbook += 1
            elif snapshot.status == "error":
                result.tokens_error += 1
                if snapshot.reason:
                    if "HTTP 429" in snapshot.reason:
                        result.tokens_http_429 += 1
                    elif "HTTP 5" in snapshot.reason:
                        result.tokens_http_5xx += 1
                result.errors.append({
                    "token_id": token_id,
                    "reason": snapshot.reason,
                })
        except Exception as exc:
            logger.error(f"Unexpected error snapshotting {token_id}: {exc}")
            result.tokens_error += 1
            exc_str = str(exc)
            result.errors.append({
                "token_id": token_id,
                "reason": exc_str,
            })

    logger.info(
        f"Snapshot complete: attempted={result.tokens_attempted}, "
        f"ok={result.tokens_ok}, empty={result.tokens_empty}, "
        f"one_sided={result.tokens_one_sided}, no_orderbook={result.tokens_no_orderbook}, "
        f"error={result.tokens_error}"
    )

    return result


def get_insert_columns() -> list[str]:
    """Get column names for ClickHouse insert."""
    return [
        "token_id",
        "snapshot_ts",
        "best_bid",
        "best_ask",
        "mid_price",
        "spread_bps",
        "depth_bid_usd_50bps",
        "depth_ask_usd_50bps",
        "slippage_buy_bps_100",
        "slippage_sell_bps_100",
        "slippage_buy_bps_500",
        "slippage_sell_bps_500",
        "levels_captured",
        "book_timestamp",
        "status",
        "reason",
        "source",
        "ingested_at",
    ]
