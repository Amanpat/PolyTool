"""Minimal CLOB client for top-of-book pricing."""

from dataclasses import dataclass
from typing import Optional
import logging

from .http_client import HttpClient

logger = logging.getLogger(__name__)

DEFAULT_CLOB_API_BASE = "https://clob.polymarket.com"


@dataclass
class OrderBookTop:
    """Best bid/ask snapshot for a token."""

    token_id: str
    best_bid: Optional[float]
    best_ask: Optional[float]
    raw_json: dict


def _extract_price(level: object) -> Optional[float]:
    if isinstance(level, dict):
        price = level.get("price") or level.get("p")
    elif isinstance(level, (list, tuple)) and level:
        price = level[0]
    else:
        price = None

    if price is None or price == "":
        return None

    try:
        return float(price)
    except (TypeError, ValueError):
        return None


@dataclass
class FeeRateInfo:
    """Fee rate information for a token."""

    token_id: str
    fee_rate_bps: float
    raw_json: dict


class ClobClient:
    """CLOB API client for order book and fee rate queries."""

    def __init__(
        self,
        base_url: str = DEFAULT_CLOB_API_BASE,
        timeout: float = 20.0,
    ):
        self.client = HttpClient(base_url=base_url, timeout=timeout)

    def get_fee_rate(self, token_id: str) -> Optional[FeeRateInfo]:
        """
        Fetch fee rate for a token from the CLOB API.

        Args:
            token_id: The token ID to query

        Returns:
            FeeRateInfo with fee_rate_bps, or None on failure
        """
        try:
            data = self.client.get_json("/fee-rate", params={"token_id": token_id})
        except Exception as exc:
            logger.warning(f"Failed to fetch fee rate for {token_id}: {exc}")
            return None

        fee_rate_bps = data.get("fee_rate_bps")
        if fee_rate_bps is None:
            # Try alternate field names
            fee_rate_bps = data.get("feeRateBps") or data.get("fee_rate") or 0

        try:
            fee_rate_bps = float(fee_rate_bps)
        except (TypeError, ValueError):
            fee_rate_bps = 0.0

        return FeeRateInfo(
            token_id=token_id,
            fee_rate_bps=fee_rate_bps,
            raw_json=data,
        )

    def fetch_book(self, token_id: str) -> dict:
        """Fetch the full order book for a token."""
        return self.client.get_json("/book", params={"token_id": token_id})

    def get_best_bid_ask(self, token_id: str) -> Optional[OrderBookTop]:
        """Fetch best bid/ask for a token from the order book."""
        try:
            book = self.fetch_book(token_id)
        except Exception as exc:
            logger.warning(f"Failed to fetch CLOB book for {token_id}: {exc}")
            return None

        bids = book.get("bids") or []
        asks = book.get("asks") or []

        best_bid = _extract_price(bids[0]) if bids else None
        best_ask = _extract_price(asks[0]) if asks else None

        return OrderBookTop(
            token_id=token_id,
            best_bid=best_bid,
            best_ask=best_ask,
            raw_json=book,
        )
