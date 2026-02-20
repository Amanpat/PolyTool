"""Minimal CLOB client for order-book and historical pricing."""

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from typing import Mapping, Optional

from .http_client import HttpClient

logger = logging.getLogger(__name__)

DEFAULT_CLOB_API_BASE = "https://clob.polymarket.com"
_LEGACY_FIDELITY_MINUTES = {
    "high": 1,
    "medium": 5,
    "low": 60,
}


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


def _coerce_fidelity_minutes(value: object) -> int:
    """Normalize fidelity to integer minute resolution expected by /prices-history."""
    if isinstance(value, (int, float)) and int(value) == value:
        minutes = int(value)
        if minutes > 0:
            return minutes
        raise ValueError(f"fidelity must be a positive integer minutes value, got: {value}")

    text = str(value or "").strip().lower()
    if not text:
        return 1
    if text in _LEGACY_FIDELITY_MINUTES:
        return _LEGACY_FIDELITY_MINUTES[text]
    if text.endswith("m") and text[:-1].isdigit():
        minutes = int(text[:-1])
    else:
        try:
            minutes = int(text)
        except ValueError as exc:
            raise ValueError(
                "fidelity must be a positive integer minutes value "
                "(or legacy high/medium/low)"
            ) from exc
    if minutes <= 0:
        raise ValueError(f"fidelity must be a positive integer minutes value, got: {value}")
    return minutes


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
        default_headers: Optional[Mapping[str, str]] = None,
    ):
        self.client = HttpClient(base_url=base_url, timeout=timeout)
        self.default_headers = {
            str(k): str(v)
            for k, v in (default_headers or {}).items()
            if str(k).strip() and str(v).strip()
        }

    def _headers(self, headers: Optional[Mapping[str, str]] = None) -> Optional[dict]:
        merged: dict[str, str] = dict(self.default_headers)
        for k, v in (headers or {}).items():
            key = str(k).strip()
            value = str(v).strip()
            if key and value:
                merged[key] = value
        return merged or None

    def has_auth_headers(self) -> bool:
        """Return True when likely auth headers are configured (no secrets exposed)."""
        auth_header_keys = {
            "authorization",
            "x-api-key",
            "api-key",
            "x-polymarket-api-key",
            "x-polymarket-signature",
            "x-polymarket-timestamp",
            "x-polymarket-address",
        }
        for key, value in self.default_headers.items():
            if str(key).strip().lower() in auth_header_keys and str(value).strip():
                return True
        return False

    def get_fee_rate(self, token_id: str) -> Optional[FeeRateInfo]:
        """
        Fetch fee rate for a token from the CLOB API.

        Args:
            token_id: The token ID to query

        Returns:
            FeeRateInfo with fee_rate_bps, or None on failure
        """
        try:
            data = self.client.get_json(
                "/fee-rate",
                params={"token_id": token_id},
                headers=self._headers(),
            )
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
        return self.client.get_json(
            "/book",
            params={"token_id": token_id},
            headers=self._headers(),
        )

    def fetch_book_response(self, token_id: str):
        """Fetch the full order book response for a token."""
        return self.client.get_response(
            "/book",
            params={"token_id": token_id},
            headers=self._headers(),
        )

    def get_prices_history(
        self,
        token_id: str,
        *,
        start_ts: Optional[datetime] = None,
        end_ts: Optional[datetime] = None,
        interval: Optional[str] = None,
        fidelity: object = 1,
    ) -> dict:
        """Fetch historical prices for a token from the CLOB API.

        Query parameters follow the CLOB `/prices-history` contract. Timestamps
        are normalized to UTC epoch seconds.
        """
        params: dict[str, object] = {
            "market": token_id,
            "fidelity": _coerce_fidelity_minutes(fidelity),
        }

        has_start = start_ts is not None
        has_end = end_ts is not None
        if has_start or has_end:
            if not (has_start and has_end):
                raise ValueError("start_ts and end_ts must be provided together for bounded history")
            start_utc = start_ts.astimezone(timezone.utc)
            end_utc = end_ts.astimezone(timezone.utc)
            params["startTs"] = int(start_utc.timestamp())
            params["endTs"] = int(end_utc.timestamp())
            # CLOB API rejects interval when startTs/endTs are present.
        else:
            interval_value = str(interval or "").strip()
            if interval_value:
                params["interval"] = interval_value

        return self.client.get_json(
            "/prices-history",
            params=params,
            headers=self._headers(),
        )

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
