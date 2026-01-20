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
class Activity:
    """Normalized activity record."""

    proxy_wallet: str
    activity_uid: str
    ts: datetime
    activity_type: str
    token_id: Optional[str]
    condition_id: Optional[str]
    size: Optional[float]
    price: Optional[float]
    tx_hash: Optional[str]
    raw_json: dict

    @classmethod
    def from_api_response(cls, data: dict, proxy_wallet: str) -> "Activity":
        """
        Create Activity from API response.

        Activity UID computation:
        - Use 'id' field if present (preferred, stable identifier)
        - Otherwise compute: sha256(proxy_wallet + ts + activity_type + token_id +
          condition_id + size + price + tx_hash)
        """
        token_id = (
            data.get("tokenId")
            or data.get("token_id")
            or data.get("asset")
            or data.get("token")
            or ""
        )
        condition_id = data.get("conditionId") or data.get("condition_id") or ""
        activity_type = (
            data.get("activityType")
            or data.get("activity_type")
            or data.get("type")
            or data.get("action")
            or ""
        )
        if isinstance(activity_type, str):
            activity_type = activity_type.upper()

        size_raw = data.get("size") or data.get("amount") or data.get("shares")
        size = float(size_raw) if size_raw is not None and size_raw != "" else None
        price_raw = data.get("price") or data.get("avgPrice") or data.get("avg_price")
        price = float(price_raw) if price_raw is not None and price_raw != "" else None
        tx_hash = (
            data.get("transactionHash")
            or data.get("txHash")
            or data.get("transaction_hash")
            or data.get("tx")
            or ""
        )

        ts_raw = (
            data.get("timestamp")
            or data.get("createdAt")
            or data.get("time")
            or data.get("blockTime")
            or ""
        )
        if isinstance(ts_raw, (int, float)):
            ts = datetime.utcfromtimestamp(ts_raw)
        elif isinstance(ts_raw, str) and ts_raw:
            try:
                ts_raw = ts_raw.replace("Z", "+00:00")
                if "T" in ts_raw:
                    ts = datetime.fromisoformat(ts_raw.replace("+00:00", ""))
                else:
                    ts = datetime.strptime(ts_raw[:19], "%Y-%m-%d %H:%M:%S")
            except ValueError:
                logger.warning(f"Could not parse activity timestamp: {ts_raw}")
                ts = datetime.utcnow()
        else:
            ts = datetime.utcnow()

        activity_id = (
            data.get("id")
            or data.get("activityId")
            or data.get("activity_id")
            or data.get("uid")
        )
        if activity_id:
            activity_uid = str(activity_id)
        else:
            uid_components = (
                f"{proxy_wallet}"
                f"{ts.isoformat()}"
                f"{activity_type}"
                f"{token_id}"
                f"{condition_id}"
                f"{size}"
                f"{price}"
                f"{tx_hash}"
            )
            activity_uid = hashlib.sha256(uid_components.encode()).hexdigest()

        return cls(
            proxy_wallet=proxy_wallet,
            activity_uid=activity_uid,
            ts=ts,
            activity_type=activity_type,
            token_id=token_id or None,
            condition_id=condition_id or None,
            size=size,
            price=price,
            tx_hash=tx_hash or None,
            raw_json=data,
        )


@dataclass
class Position:
    """Normalized position record."""

    proxy_wallet: str
    token_id: str
    condition_id: Optional[str]
    outcome: Optional[str]
    shares: float
    avg_cost: Optional[float]
    raw_json: dict

    @classmethod
    def from_api_response(cls, data: dict, proxy_wallet: str) -> "Position":
        token_id = (
            data.get("tokenId")
            or data.get("token_id")
            or data.get("asset")
            or data.get("token")
            or ""
        )
        condition_id = data.get("conditionId") or data.get("condition_id") or ""
        outcome = (
            data.get("outcome")
            or data.get("outcomeName")
            or data.get("outcome_name")
            or data.get("side")
            or ""
        )
        shares_raw = (
            data.get("shares")
            or data.get("size")
            or data.get("position")
            or data.get("amount")
            or 0
        )
        try:
            shares = float(shares_raw)
        except (TypeError, ValueError):
            shares = 0.0

        avg_cost_raw = (
            data.get("avgCost")
            or data.get("avg_cost")
            or data.get("avgPrice")
            or data.get("avg_price")
            or data.get("costBasis")
        )
        avg_cost = float(avg_cost_raw) if avg_cost_raw is not None and avg_cost_raw != "" else None

        return cls(
            proxy_wallet=proxy_wallet,
            token_id=token_id,
            condition_id=condition_id or None,
            outcome=outcome or None,
            shares=shares,
            avg_cost=avg_cost,
            raw_json=data,
        )


@dataclass
class TradesFetchResult:
    """Result of fetching trades."""

    trades: list[Trade] = field(default_factory=list)
    pages_fetched: int = 0
    total_rows: int = 0


@dataclass
class ActivityFetchResult:
    """Result of fetching activity."""

    activities: list[Activity] = field(default_factory=list)
    pages_fetched: int = 0
    total_rows: int = 0


@dataclass
class PositionsFetchResult:
    """Result of fetching positions."""

    positions: list[Position] = field(default_factory=list)
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

    def fetch_activity_page(
        self,
        proxy_wallet: str,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[dict]:
        """
        Fetch a single page of activity entries.

        Args:
            proxy_wallet: User's proxy wallet address
            limit: Number of activities per page
            offset: Offset for pagination

        Returns:
            List of raw activity dictionaries
        """
        logger.debug(f"Fetching activity: wallet={proxy_wallet[:10]}..., offset={offset}")

        try:
            response = self.client.get_json(
                "/activity",
                params={
                    "user": proxy_wallet,
                    "limit": min(limit, 1000),
                    "offset": offset,
                },
            )
        except Exception as e:
            logger.error(f"Error fetching activity page (offset={offset}): {e}")
            raise

        if isinstance(response, list):
            return response
        elif isinstance(response, dict):
            return response.get("data", response.get("activity", []))
        else:
            logger.warning(f"Unexpected response type: {type(response)}")
            return []

    def fetch_all_activity(
        self,
        proxy_wallet: str,
        max_pages: int = 50,
        page_size: int = 1000,
    ) -> ActivityFetchResult:
        """
        Fetch all activity for a user with pagination.

        Args:
            proxy_wallet: User's proxy wallet address
            max_pages: Maximum number of pages to fetch
            page_size: Activities per page

        Returns:
            ActivityFetchResult with all fetched activity
        """
        result = ActivityFetchResult()
        offset = 0

        for page in range(max_pages):
            logger.info(
                f"Fetching activity page {page + 1}/{max_pages} "
                f"(offset={offset}, wallet={proxy_wallet[:10]}...)"
            )

            try:
                raw_activity = self.fetch_activity_page(
                    proxy_wallet=proxy_wallet,
                    limit=page_size,
                    offset=offset,
                )
            except Exception as e:
                logger.error(f"Failed to fetch activity page {page + 1}: {e}")
                break

            result.pages_fetched += 1

            if not raw_activity:
                logger.info(f"Empty activity page at offset {offset}, stopping")
                break

            for raw in raw_activity:
                try:
                    activity = Activity.from_api_response(raw, proxy_wallet)
                    result.activities.append(activity)
                    result.total_rows += 1
                except Exception as e:
                    logger.warning(f"Failed to parse activity: {e}")
                    continue

            if len(raw_activity) < page_size:
                logger.info(
                    f"Received {len(raw_activity)} activity rows (< {page_size}), "
                    f"likely last page"
                )
                break

            offset += page_size

        logger.info(
            f"Activity fetch complete: {result.pages_fetched} pages, "
            f"{result.total_rows} rows"
        )

        return result

    def fetch_positions(
        self,
        proxy_wallet: str,
    ) -> PositionsFetchResult:
        """
        Fetch current positions for a user.

        Args:
            proxy_wallet: User's proxy wallet address

        Returns:
            PositionsFetchResult with fetched positions
        """
        result = PositionsFetchResult()

        try:
            response = self.client.get_json(
                "/positions",
                params={"user": proxy_wallet},
            )
        except Exception as e:
            logger.error(f"Error fetching positions: {e}")
            return result

        if isinstance(response, list):
            raw_positions = response
        elif isinstance(response, dict):
            raw_positions = response.get("data", response.get("positions", []))
        else:
            logger.warning(f"Unexpected response type: {type(response)}")
            raw_positions = []

        for raw in raw_positions:
            try:
                position = Position.from_api_response(raw, proxy_wallet)
                result.positions.append(position)
                result.total_rows += 1
            except Exception as e:
                logger.warning(f"Failed to parse position: {e}")
                continue

        logger.info(f"Fetched {result.total_rows} positions for {proxy_wallet[:10]}...")
        return result

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
