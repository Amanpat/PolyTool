"""Data API client for Polymarket trade history."""

import hashlib
import json
import logging
from typing import Iterator, Optional
from dataclasses import dataclass, field
from datetime import datetime

from .http_client import HttpClient

logger = logging.getLogger(__name__)

# Default Data API base URL
DEFAULT_DATA_API_BASE = "https://data-api.polymarket.com"


@dataclass
class Trade:
    """Normalized trade record."""

    proxy_wallet: str
    trade_uid: str
    ts: datetime
    token_id: str
    condition_id: str
    outcome: str
    side: str
    size: float
    price: float
    transaction_hash: str
    raw_json: dict

    @classmethod
    def from_api_response(cls, data: dict, proxy_wallet: str) -> "Trade":
        """
        Create Trade from API response.

        Trade UID computation:
        - Use 'id' field if present (preferred, stable identifier)
        - Otherwise compute: sha256(proxy_wallet + ts + token_id + side + size + price + transaction_hash + outcome + condition_id)

        Args:
            data: Raw trade data from API
            proxy_wallet: User's proxy wallet address

        Returns:
            Normalized Trade object
        """
        # Extract fields with fallbacks
        token_id = data.get("asset", "") or data.get("token_id", "") or data.get("tokenId", "") or ""
        condition_id = data.get("conditionId", "") or data.get("condition_id", "") or ""
        outcome = data.get("outcome", "") or data.get("outcomeName", "") or ""
        side = data.get("side", "") or data.get("type", "") or ""
        size = float(data.get("size", 0) or data.get("amount", 0) or 0)
        price = float(data.get("price", 0) or data.get("avgPrice", 0) or 0)
        transaction_hash = data.get("transactionHash", "") or data.get("txHash", "") or data.get("transaction_hash", "") or ""

        # Parse timestamp
        ts_raw = data.get("timestamp") or data.get("createdAt") or data.get("matchTime") or ""
        if isinstance(ts_raw, (int, float)):
            # Unix timestamp
            ts = datetime.utcfromtimestamp(ts_raw)
        elif isinstance(ts_raw, str) and ts_raw:
            # ISO format or similar
            try:
                # Handle various formats
                ts_raw = ts_raw.replace("Z", "+00:00")
                if "T" in ts_raw:
                    ts = datetime.fromisoformat(ts_raw.replace("+00:00", ""))
                else:
                    ts = datetime.strptime(ts_raw[:19], "%Y-%m-%d %H:%M:%S")
            except ValueError:
                logger.warning(f"Could not parse timestamp: {ts_raw}")
                ts = datetime.utcnow()
        else:
            ts = datetime.utcnow()

        # Compute trade_uid
        # Prefer 'id' field if present
        trade_id = data.get("id") or data.get("tradeId") or data.get("trade_id")
        if trade_id:
            trade_uid = str(trade_id)
        else:
            # Compute stable hash
            # Format: sha256(proxy_wallet + ts + token_id + side + size + price + transaction_hash + outcome + condition_id)
            uid_components = (
                f"{proxy_wallet}"
                f"{ts.isoformat()}"
                f"{token_id}"
                f"{side}"
                f"{size}"
                f"{price}"
                f"{transaction_hash}"
                f"{outcome}"
                f"{condition_id}"
            )
            trade_uid = hashlib.sha256(uid_components.encode()).hexdigest()

        return cls(
            proxy_wallet=proxy_wallet,
            trade_uid=trade_uid,
            ts=ts,
            token_id=token_id,
            condition_id=condition_id,
            outcome=outcome,
            side=side,
            size=size,
            price=price,
            transaction_hash=transaction_hash,
            raw_json=data,
        )


@dataclass
class TradesFetchResult:
    """Result of fetching trades."""

    trades: list[Trade] = field(default_factory=list)
    pages_fetched: int = 0
    total_rows: int = 0


class DataApiClient:
    """Client for Polymarket Data API (trade history)."""

    def __init__(
        self,
        base_url: str = DEFAULT_DATA_API_BASE,
        timeout: float = 20.0,
    ):
        """
        Initialize Data API client.

        Args:
            base_url: Data API base URL
            timeout: Request timeout in seconds
        """
        self.client = HttpClient(base_url=base_url, timeout=timeout)

    def fetch_trades_page(
        self,
        proxy_wallet: str,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[dict]:
        """
        Fetch a single page of trades.

        Args:
            proxy_wallet: User's proxy wallet address
            limit: Number of trades per page (max 1000)
            offset: Offset for pagination

        Returns:
            List of raw trade dictionaries
        """
        logger.debug(f"Fetching trades: wallet={proxy_wallet[:10]}..., offset={offset}")

        try:
            response = self.client.get_json(
                "/trades",
                params={
                    "user": proxy_wallet,
                    "limit": min(limit, 1000),
                    "offset": offset,
                },
            )
        except Exception as e:
            logger.error(f"Error fetching trades page (offset={offset}): {e}")
            raise

        # Response is typically a list of trades
        if isinstance(response, list):
            return response
        elif isinstance(response, dict):
            # Some APIs wrap in { "data": [...] } or { "trades": [...] }
            return response.get("data", response.get("trades", []))
        else:
            logger.warning(f"Unexpected response type: {type(response)}")
            return []

    def fetch_all_trades(
        self,
        proxy_wallet: str,
        max_pages: int = 50,
        page_size: int = 1000,
    ) -> TradesFetchResult:
        """
        Fetch all trades for a user with pagination.

        Args:
            proxy_wallet: User's proxy wallet address
            max_pages: Maximum number of pages to fetch
            page_size: Number of trades per page

        Returns:
            TradesFetchResult with all fetched trades
        """
        result = TradesFetchResult()
        offset = 0

        for page in range(max_pages):
            logger.info(
                f"Fetching page {page + 1}/{max_pages} "
                f"(offset={offset}, wallet={proxy_wallet[:10]}...)"
            )

            try:
                raw_trades = self.fetch_trades_page(
                    proxy_wallet=proxy_wallet,
                    limit=page_size,
                    offset=offset,
                )
            except Exception as e:
                logger.error(f"Failed to fetch page {page + 1}: {e}")
                break

            result.pages_fetched += 1

            if not raw_trades:
                logger.info(f"Empty page received at offset {offset}, stopping")
                break

            # Convert to Trade objects
            for raw_trade in raw_trades:
                try:
                    trade = Trade.from_api_response(raw_trade, proxy_wallet)
                    result.trades.append(trade)
                    result.total_rows += 1
                except Exception as e:
                    logger.warning(f"Failed to parse trade: {e}")
                    continue

            # Check if we got fewer than requested (last page)
            if len(raw_trades) < page_size:
                logger.info(
                    f"Received {len(raw_trades)} trades (< {page_size}), "
                    f"likely last page"
                )
                break

            offset += page_size

        logger.info(
            f"Fetch complete: {result.pages_fetched} pages, "
            f"{result.total_rows} trades"
        )

        return result

    def iter_trades(
        self,
        proxy_wallet: str,
        max_pages: int = 50,
        page_size: int = 1000,
    ) -> Iterator[Trade]:
        """
        Iterate over trades for a user (memory-efficient).

        Args:
            proxy_wallet: User's proxy wallet address
            max_pages: Maximum number of pages to fetch
            page_size: Number of trades per page

        Yields:
            Trade objects one at a time
        """
        offset = 0

        for page in range(max_pages):
            try:
                raw_trades = self.fetch_trades_page(
                    proxy_wallet=proxy_wallet,
                    limit=page_size,
                    offset=offset,
                )
            except Exception:
                break

            if not raw_trades:
                break

            for raw_trade in raw_trades:
                try:
                    yield Trade.from_api_response(raw_trade, proxy_wallet)
                except Exception:
                    continue

            if len(raw_trades) < page_size:
                break

            offset += page_size
